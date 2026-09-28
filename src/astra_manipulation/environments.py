"""Simulator boundaries: only camera pixels and robot proprioception reach policy."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .core import Observation


class LiftEnvironment:
    def __init__(self, instruction: str, dataset_path: str | None = None, max_steps: int = 400):
        os.environ.setdefault("MUJOCO_GL", "egl")
        import robosuite
        from robosuite.controllers import load_part_controller_config
        from robosuite.controllers.composite.composite_controller_factory import refactor_composite_controller_config

        self.instruction, self.max_steps = instruction, max_steps
        self.dataset_path = dataset_path
        self.step_index = 0
        kwargs = {}
        if dataset_path:
            import h5py
            with h5py.File(dataset_path, "r") as data:
                metadata = json.loads(data["data"].attrs["env_args"])
            if metadata["env_name"] != "Lift":
                raise ValueError("The gripper adapter requires a Lift dataset")
            kwargs.update(metadata["env_kwargs"])
        kwargs.update(robots="Panda", has_renderer=False, has_offscreen_renderer=True,
                      use_camera_obs=True, use_object_obs=False, camera_names=["agentview", "robot0_eye_in_hand"],
                      camera_heights=256, camera_widths=256, camera_depths=False,
                      reward_shaping=False, horizon=max_steps, ignore_done=False,
                      control_freq=20,
                      controller_configs=refactor_composite_controller_config(
                          load_part_controller_config(default_controller="OSC_POSE"), "Panda", ["right"]))
        self.env = robosuite.make("Lift", **kwargs)
        low, high = self.env.action_spec
        self.action_spec = {
            "names": ["delta_x", "delta_y", "delta_z", "delta_rx", "delta_ry", "delta_rz", "gripper"],
            "low": low.tolist(), "high": high.tolist(), "dimension": len(low),
            "control_dt": 1 / self.env.control_freq,
            "semantics": "Normalized base-frame end-effector pose deltas. Translation scale 0.05 meters; rotation scale 0.5 radians. Gripper -1 opens, +1 closes. Each command advances one control interval.",
        }
        if len(low) != 7:
            raise RuntimeError(f"Expected 7 Lift actions, got {len(low)}")

    def _observation(self, raw):
        # Whitelist avoids robot0_proprio-state composites or task observables.
        keys = ("robot0_joint_pos", "robot0_joint_pos_cos", "robot0_joint_pos_sin",
                "robot0_joint_vel", "robot0_eef_pos", "robot0_eef_quat",
                "robot0_gripper_qpos", "robot0_gripper_qvel")
        proprio = {key: np.asarray(raw[key]).reshape(-1).tolist() for key in keys if key in raw}
        from robosuite import macros
        images = {}
        for name in ("agentview", "robot0_eye_in_hand"):
            frame = np.asarray(raw[name + "_image"], dtype=np.uint8)
            # Robosuite defaults to OpenGL's upside-down array convention.
            if macros.IMAGE_CONVENTION == "opengl":
                frame = frame[::-1]
            images[name] = frame.copy()
        return Observation(images=images, proprioception=proprio, instruction=self.instruction,
                           step_index=self.step_index)

    def reset(self, seed: int, episode_id: int | None = None):
        np.random.seed(seed)
        self.env.seed = seed
        self.env.rng = np.random.default_rng(seed)
        self.step_index = 0
        raw = self.env.reset()
        if episode_id is not None:
            if not self.dataset_path:
                raise ValueError("episode_id requires a robomimic dataset_path")
            import h5py
            with h5py.File(self.dataset_path, "r") as data:
                demo = data["data"][f"demo_{episode_id}"]
                model = demo.attrs["model_file"]
                state = demo["states"][0]
            if isinstance(model, bytes):
                model = model.decode()
            self.env.reset_from_xml_string(self.env.edit_model_xml(model))
            self.env.sim.reset()
            self.env.sim.set_state_from_flattened(state)
            self.env.sim.forward()
            raw = self.env._get_observations(force_update=True)
        return self._observation(raw)

    def step(self, action: list[float]):
        raw, reward, done, _ = self.env.step(np.asarray(action, dtype=float))
        self.step_index += 1
        metrics = {"success": bool(self.env._check_success()), "reward": float(reward)}
        return self._observation(raw), bool(done or self.step_index >= self.max_steps), metrics

    def close(self):
        self.env.close()


class AdroitEnvironment:
    def __init__(self, instruction: str, dataset_path: str | None = None, max_steps: int = 400):
        os.environ.setdefault("MUJOCO_GL", "egl")
        import gymnasium as gym
        import gymnasium_robotics
        import mujoco

        gym.register_envs(gymnasium_robotics)
        self.instruction, self.max_steps = instruction, max_steps
        self.dataset_path, self.step_index = dataset_path, 0
        self.env = gym.make("AdroitHandRelocate-v1", render_mode="rgb_array", width=384,
                            height=384, max_episode_steps=max_steps)
        model = self.env.unwrapped.model
        names = [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, i) for i in range(model.nu)]
        joint_ids = model.actuator_trnid[:, 0]
        self._robot_qvel_indices = model.jnt_dofadr[joint_ids].copy()
        qpos_indices = model.jnt_qposadr[joint_ids]
        if not np.array_equal(qpos_indices, np.arange(30)):
            raise RuntimeError("Adroit robot observation ordering differs from audited actuator ordering")
        if not np.array_equal(self._robot_qvel_indices, np.arange(30)):
            raise RuntimeError("Adroit velocity ordering differs from audited actuator ordering")
        if not np.all(model.actuator_gear[:, 0] == 1):
            raise RuntimeError("Adroit actuator gearing differs from audited unit gearing")
        self._palm_site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "S_grasp")
        forearm_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "forearm")
        if model.body_parentid[forearm_id] != 0:
            raise RuntimeError("Adroit forearm no longer directly attached to world")
        base_rotation = np.empty(9)
        mujoco.mju_quat2Mat(base_rotation, model.body_quat[forearm_id])
        translation_axes = (base_rotation.reshape(3, 3) @ model.jnt_axis[joint_ids[:3]].T).T
        gain = model.actuator_gainprm[:, 0]
        position_bias = model.actuator_biasprm[:, 1]
        equilibrium_scale = -gain / position_bias
        descriptions = [
            "Arm local X translation: positive moves approximately world -X (horizontal).",
            "Arm local Y translation: positive moves approximately world +Z (UP).",
            "Arm local Z translation: positive moves approximately world +Y (horizontal), NOT up.",
            "Arm rotation around local X (radians); axis depends on preceding joint rotations.",
            "Arm rotation around local Y (radians); axis depends on preceding joint rotations.",
            "Arm rotation around local Z (radians); axis depends on preceding joint rotations.",
            "Wrist radial/ulnar deviation (WRJ1).", "Wrist flexion/extension (WRJ0).",
        ]
        finger_names = {"FF": "index", "MF": "middle", "RF": "ring", "LF": "little", "TH": "thumb"}
        descriptions.extend(f"{finger_names[name[2:4]]} finger joint {name[2:]}; positive increases that joint coordinate."
                            for name in names[8:])
        self.action_spec = {
            "spec_version": "adroit-actuator-audit-v2",
            "names": names, "low": self.env.action_space.low.tolist(),
            "high": self.env.action_space.high.tolist(), "dimension": model.nu,
            "control_dt": float(self.env.unwrapped.dt),
            "descriptions": descriptions,
            "control_ranges": model.actuator_ctrlrange.tolist(),
            "joint_coordinate_limits": model.jnt_range[joint_ids].tolist(),
            "joint_position_indices": qpos_indices.tolist(),
            "actuator_gain": gain.tolist(),
            "actuator_position_bias": position_bias.tolist(),
            "actuator_velocity_bias": model.actuator_biasprm[:, 2].tolist(),
            "actuator_constant_bias": model.actuator_biasprm[:, 0].tolist(),
            "no_load_equilibrium_scale": equilibrium_scale.tolist(),
            "arm_translation_positive_axes_world": translation_axes.tolist(),
            "semantics": "30 normalized actuator controls, NOT direct joint-position targets. u = control_range_midpoint + action * control_range_halfwidth. Actuator force = gain*u + constant_bias + position_bias*q + velocity_bias*qdot (unit gear). Ignoring gravity/contact/passive forces, equilibrium q = -gain/position_bias*u: first SIX arm joints q_eq=2.5*u; wrist/fingers q_eq=u. To approximately hold measured q without external loads: u=q/no_load_equilibrium_scale, then action=(u-midpoint)/halfwidth, bounded [-1,1]. Actual equilibrium can differ under loads and joint limits. First 3 q values are LOCAL translations in meters; local Y raises/lowers the arm, local Z moves horizontally. Last 27 q values are radians. Zero action means control-range midpoint, NOT hold. One step advances control_dt. Palm pose is robot-only forward kinematics in world coordinates; rotation matrix is row-major, with columns giving local palm-site axes in world.",
        }

    def _observation(self, raw):
        # Adroit's last nine observation entries are privileged relative object/goal positions.
        joints = np.asarray(raw)[:30].copy()
        data = self.env.unwrapped.data
        proprioception = {
            "joint_positions": joints.tolist(),
            "joint_velocities": data.qvel[self._robot_qvel_indices].copy().tolist(),
            "palm_site_position_world": data.site_xpos[self._palm_site_id].copy().tolist(),
            "palm_site_rotation_world_rowmajor": data.site_xmat[self._palm_site_id].copy().reshape(-1).tolist(),
        }
        return Observation(images={"external": self.env.render().copy()},
                           proprioception=proprioception,
                           instruction=self.instruction, step_index=self.step_index)

    def reset(self, seed: int, episode_id: int | None = None):
        options = None
        if episode_id is not None:
            if not self.dataset_path or Path(self.dataset_path).suffix != ".json":
                raise ValueError("Adroit episode reset requires the converted original hand_dapg initial-state JSON; Minari alone has no reset states")
            with Path(self.dataset_path).open() as handle:
                dataset = json.load(handle)
            if dataset.get("dataset") != "hand_dapg/relocate-v0":
                raise ValueError("Expected converted hand_dapg relocation initial states")
            if not 0 <= episode_id < len(dataset["episodes"]):
                raise ValueError("Adroit episode index out of range")
            state = {key: np.asarray(value, dtype=np.float64)
                     for key, value in dataset["episodes"][episode_id].items()}
            # v1's set_env_state incorrectly offsets nonzero object translations.
            # The reviewed demonstration initial states have zero object translations.
            if np.any(state["qpos"][-6:-3] != 0):
                raise ValueError("v1 restoration requires zero initial object joint translations")
            options = {"initial_state_dict": state}
        self.step_index = 0
        raw, _ = self.env.reset(seed=seed, options=options)
        return self._observation(raw)

    def step(self, action: list[float]):
        raw, reward, terminated, truncated, info = self.env.step(np.asarray(action, dtype=np.float32))
        self.step_index += 1
        metrics = {"success": bool(info.get("success", False)), "reward": float(reward)}
        return self._observation(raw), bool(terminated or truncated), metrics

    def close(self):
        self.env.close()


def make_environment(backend: str, instruction: str, dataset_path: str | None = None, max_steps: int = 400):
    if backend in {"lift", "gripper", "robosuite"}:
        return LiftEnvironment(instruction, dataset_path, max_steps)
    if backend in {"adroit", "dexterous", "relocate"}:
        return AdroitEnvironment(instruction, dataset_path, max_steps)
    raise ValueError(f"Unknown environment backend {backend!r}")

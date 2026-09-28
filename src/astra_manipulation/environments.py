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
        self.action_spec = {
            "names": names, "low": self.env.action_space.low.tolist(),
            "high": self.env.action_space.high.tolist(), "dimension": model.nu,
            "control_dt": float(self.env.unwrapped.dt),
            "joint_target_ranges": model.actuator_ctrlrange.tolist(),
            "semantics": "30 normalized absolute joint-position targets: target = midpoint + action * half_range. First 3 are arm XYZ translations (meters), next 3 arm rotations (radians), then wrist and finger joints. See joint_target_ranges in the same order as names. Zero means range midpoint, NOT hold current position. Each command advances one control interval.",
        }

    def _observation(self, raw):
        # Adroit's last nine observation entries are privileged relative object/goal positions.
        joints = np.asarray(raw)[:30].copy()
        return Observation(images={"external": self.env.render().copy()},
                           proprioception={"joint_positions": joints.tolist()},
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

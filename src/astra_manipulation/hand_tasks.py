"""Five hand tasks with explicit robot-only sensing and fixed calibrated cameras."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from .core import Observation

HAND_TASKS = {
    "relocate": {"env_id": "AdroitHandRelocate-v1", "instruction": "Grasp the blue ball and carry it into the visible green target region.", "success": "native object-target distance below 0.10 m"},
    "door": {"env_id": "AdroitHandDoor-v1", "instruction": "Use the hand to unlatch the handle and swing the door open wide.", "success": "native door hinge angle at least 1.35 radians"},
    "hammer": {"env_id": "AdroitHandHammer-v1", "instruction": "Grasp the hammer and use it to drive the nail fully into the board.", "success": "native nail-to-goal distance below 0.01 m"},
    "pen": {"env_id": "AdroitHandPen-v1", "instruction": "Reorient the blue pen in the hand to match the orientation of the visible green reference pen, keeping the blue pen in hand.", "success": "native pen goal proximity and orientation alignment"},
    "ball_lift": {"env_id": "AdroitHandRelocate-v1", "instruction": "Grasp the blue ball and lift its center above 10 cm from the tabletop; keep it raised for at least five control steps.", "success": "object center world z above 0.10 m for five consecutive steps; tabletop is z=0"},
}

# Presets are fixed before reset and never depend on scene object positions.
CAMERA_PRESETS = {
    "relocate": ((0.0, 0.0, 0.20), 1.20),
    "ball_lift": ((0.0, 0.0, 0.20), 1.20),
    "door": ((0.0, -0.10, 0.23), 1.05),
    "hammer": ((0.0, -0.12, 0.23), 1.00),
    "pen": ((0.0, -0.12, 0.23), 0.80),
}


def robot_actuator_mapping(model, mujoco):
    """Resolve each actuator's robot joint, refusing object joints or ambiguous gears."""
    names, joint_ids = [], []
    forearm = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "forearm")
    if forearm < 0:
        raise ValueError("Expected an Adroit forearm robot root")
    for index in range(model.nu):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_ACTUATOR, index)
        if not name.startswith("A_") or model.actuator_trntype[index] != mujoco.mjtTrn.mjTRN_JOINT:
            raise ValueError("Nonrobot or unsupported actuator transmission")
        joint = int(model.actuator_trnid[index, 0])
        body = int(model.jnt_bodyid[joint])
        while body and body != forearm:
            body = int(model.body_parentid[body])
        if body != forearm or model.jnt_type[joint] not in (mujoco.mjtJoint.mjJNT_SLIDE, mujoco.mjtJoint.mjJNT_HINGE):
            raise ValueError("Actuator does not address a scalar robot joint")
        if not np.array_equal(model.actuator_gear[index], [1, 0, 0, 0, 0, 0]):
            raise ValueError("Unsupported actuator gearing")
        names.append(name)
        joint_ids.append(joint)
    return names, np.asarray(joint_ids, dtype=int)


class HandTaskEnvironment:
    def __init__(self, task, instruction=None, dataset_path=None, max_steps=600, image_size=768):
        if task not in HAND_TASKS:
            raise ValueError(f"Unknown hand task {task!r}")
        os.environ.setdefault("MUJOCO_GL", "osmesa")
        import gymnasium as gym
        import gymnasium_robotics
        import mujoco
        self._mj = mujoco
        gym.register_envs(gymnasium_robotics)
        self.task, self.dataset_path = task, dataset_path
        self.instruction = instruction or HAND_TASKS[task]["instruction"]
        self.step_index, self._height_hold = 0, 0
        self.env = gym.make(HAND_TASKS[task]["env_id"], max_episode_steps=max_steps)
        self._u = self.env.unwrapped
        model = self._u.model
        names, joints = robot_actuator_mapping(model, mujoco)
        self._qpos = model.jnt_qposadr[joints].copy()
        self._qvel = model.jnt_dofadr[joints].copy()
        self._palm = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "S_grasp")
        if self._palm < 0:
            raise ValueError("Robot palm site missing")
        if task == "ball_lift":
            # Goal marker is irrelevant for pure lifting, so hide it persistently.
            model.site_rgba[self._u.target_obj_site_id, 3] = 0
        gain = model.actuator_gainprm[:, 0]
        bias = model.actuator_biasprm
        if np.any(bias[:, 1] == 0):
            raise ValueError("Unsupported zero stiffness actuator")
        axes = {}
        for index, joint in enumerate(joints):
            if model.jnt_type[joint] == mujoco.mjtJoint.mjJNT_SLIDE:
                body = int(model.jnt_bodyid[joint])
                if model.body_parentid[body] != 0:
                    raise ValueError("Expected world-rooted arm slide")
                rotation = np.empty(9)
                mujoco.mju_quat2Mat(rotation, model.body_quat[body])
                axes[names[index]] = (rotation.reshape(3, 3) @ model.jnt_axis[joint]).tolist()
        self.action_spec = {
            "spec_version": "adroit-five-task-v1", "task": task, "names": names,
            "low": self.env.action_space.low.tolist(), "high": self.env.action_space.high.tolist(),
            "dimension": model.nu, "control_dt": float(self._u.dt),
            "control_ranges": model.actuator_ctrlrange.tolist(),
            "joint_names": [mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, int(j)) for j in joints],
            "joint_position_indices": self._qpos.tolist(), "joint_velocity_indices": self._qvel.tolist(),
            "joint_units": ["meters" if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_SLIDE else "radians" for j in joints],
            "joint_coordinate_limits": model.jnt_range[joints].tolist(),
            "actuator_gain": gain.tolist(), "actuator_constant_bias": bias[:, 0].tolist(),
            "actuator_position_bias": bias[:, 1].tolist(), "actuator_velocity_bias": bias[:, 2].tolist(),
            "no_load_equilibrium_scale": (-gain / bias[:, 1]).tolist(),
            "translation_positive_axes_world": axes,
            "semantics": "Commands are normalized actuator controls, not literal joint targets. u=midpoint(control_ranges)+action*halfwidth(control_ranges). Actuator force=gain*u+constant_bias+position_bias*q+velocity_bias*qdot. Unit gears. Ignoring loads, q_equilibrium=-(gain*u+constant_bias)/position_bias. Approximate static hold: u=-(position_bias*q+constant_bias)/gain, then normalize and clip to [-1,1]. Do not apply actions for nonexistent joints: names give the complete available set. ARTx/y/z are local arm translations; ARTy is approximately world UP, ARTz approximately world+Y horizontal, ARTx approximately world-X. The axis dictionary gives exact mappings. ARR are local arm rotations; WR are wrist, FF=index, MF=middle, RF=ring, LF=little, TH=thumb. Finger positive action increases that joint coordinate. Zero normalized action is range midpoint, not hold. Contact/gravity/passive forces and limits alter equilibrium. Proprioception is in actuator order; velocities have the corresponding units per second. Palm pose is world-frame robot FK, rotation row-major. Cameras are fixed world views with calibration below.",
        }
        model.vis.global_.offwidth = max(image_size, model.vis.global_.offwidth)
        model.vis.global_.offheight = max(image_size, model.vis.global_.offheight)
        self._renderer = mujoco.Renderer(model, height=image_size, width=image_size)
        self._cameras = {}
        center, distance = CAMERA_PRESETS[task]
        for name, azimuth, elevation in (("front", 90, -25), ("oblique", -35, -40)):
            camera = mujoco.MjvCamera()
            mujoco.mjv_defaultCamera(camera)
            camera.type = mujoco.mjtCamera.mjCAMERA_FREE
            camera.lookat[:] = center
            camera.distance, camera.azimuth, camera.elevation = distance, azimuth, elevation
            if task == "door" and name == "oblique":
                camera.distance = 1.40
                camera.lookat[:] = (0.0, 0.0, 0.30)
            self._cameras[name] = camera
        self.action_spec["camera_calibration"] = self._camera_calibration(image_size)

    def _camera_calibration(self, image_size):
        calibration = {}
        for name, camera in self._cameras.items():
            self._renderer.update_scene(self._u.data, camera=camera)
            stereo = self._renderer.scene.camera
            position = (stereo[0].pos + stereo[1].pos) / 2
            forward, up = stereo[0].forward.copy(), stereo[0].up.copy()
            focal = image_size / (2 * np.tan(np.deg2rad(self._u.model.vis.global_.fovy) / 2))
            calibration[name] = {"width": image_size, "height": image_size,
                "position_world": position.tolist(), "forward_world": forward.tolist(), "up_world": up.tolist(),
                "intrinsics_fx_fy_cx_cy": [float(focal), float(focal), image_size / 2, image_size / 2],
                "projection": "perspective; pixel x right,y down; no distortion; fixed before episode reset"}
        return calibration

    def _observation(self):
        data = self._u.data
        images = {}
        for name, camera in self._cameras.items():
            self._renderer.update_scene(data, camera=camera)
            images[name] = self._renderer.render().copy()
        return Observation(images=images, proprioception={
            "joint_positions": data.qpos[self._qpos].copy().tolist(),
            "joint_velocities": data.qvel[self._qvel].copy().tolist(),
            "palm_site_position_world": data.site_xpos[self._palm].copy().tolist(),
            "palm_site_rotation_world_rowmajor": data.site_xmat[self._palm].copy().reshape(-1).tolist(),
        }, instruction=self.instruction, step_index=self.step_index)

    def reset(self, seed, episode_id=None):
        options = None
        if episode_id is not None:
            if self.task not in ("relocate", "ball_lift") or self.dataset_path is None:
                raise ValueError("Recorded episode reset is supported only for relocate/ball_lift with initial-state JSON")
            dataset = json.loads(Path(self.dataset_path).read_text())
            if dataset.get("dataset") != "hand_dapg/relocate-v0" or not 0 <= episode_id < len(dataset["episodes"]):
                raise ValueError("Invalid relocation initial-state dataset or episode")
            state = {k: np.asarray(v, dtype=np.float64) for k, v in dataset["episodes"][episode_id].items()}
            if np.any(state["qpos"][-6:-3] != 0):
                raise ValueError("v1 initial object translation must be zero")
            options = {"initial_state_dict": state}
        self.step_index, self._height_hold = 0, 0
        self.env.reset(seed=seed, options=options)
        return self._observation()

    def step(self, action):
        _, reward, terminated, truncated, info = self.env.step(np.asarray(action, dtype=np.float32))
        self.step_index += 1
        metrics = {"success": bool(info.get("success", False)), "reward": float(reward)}
        if self.task in ("relocate", "ball_lift"):
            obj = self._u.data.xpos[self._u.obj_body_id]
            metrics["ball_height_m"] = float(obj[2])
            metrics["palm_to_ball_distance_m"] = float(np.linalg.norm(self._u.data.site_xpos[self._palm] - obj))
            if self.task == "ball_lift":
                self._height_hold = self._height_hold + 1 if obj[2] > 0.10 else 0
                metrics.update(success=self._height_hold >= 5, height_hold_steps=self._height_hold)
        elif self.task == "door":
            metrics["door_hinge_angle_rad"] = float(self._u.data.qpos[self._u.door_hinge_addrs])
        elif self.task == "hammer":
            metrics["nail_to_goal_distance_m"] = float(np.linalg.norm(
                self._u.data.site_xpos[self._u.target_obj_site_id] - self._u.data.site_xpos[self._u.goal_site_id]))
        elif self.task == "pen":
            d = self._u.data
            obj_axis = (d.site_xpos[self._u.obj_t_site_id] - d.site_xpos[self._u.obj_b_site_id]) / self._u.pen_length
            target_axis = (d.site_xpos[self._u.tar_t_site_id] - d.site_xpos[self._u.tar_b_site_id]) / self._u.tar_length
            metrics["pen_orientation_similarity"] = float(np.dot(obj_axis, target_axis))
            metrics["pen_goal_distance_m"] = float(np.linalg.norm(d.xpos[self._u.obj_body_id] - d.site_xpos[self._u.eps_ball_site_id]))
        return self._observation(), bool(terminated or truncated), metrics

    def close(self):
        self._renderer.close()
        self.env.close()

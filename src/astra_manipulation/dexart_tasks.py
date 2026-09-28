"""DexArt/SAPIEN tasks with RGB and explicitly enumerated robot sensing only.

Upstream dependencies are imported only when constructing an environment. Native
observations are disabled; task-object state is used only by the native evaluator.
"""
from __future__ import annotations

import importlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import random
import sys
import subprocess
import xml.etree.ElementTree as ET

import numpy as np

from .core import Observation


ROBOT_NAME = "allegro_hand_xarm6_wrist_mounted_face_front"
DEXART_TASKS = {
    "faucet": {"asset_id": 148, "class": "FaucetRLEnv", "instruction":
               "Reach the faucet handle, grasp it with the Allegro hand, and turn the faucet on while maintaining the grasp."},
    "laptop": {"asset_id": 11395, "class": "LaptopRLEnv", "instruction":
               "Use the Allegro hand to open the laptop lid fully."},
    "bucket": {"asset_id": 100431, "class": "BucketRLEnv", "instruction":
               "Grasp the bucket handle and lift the bucket by its handle, keeping the bucket upright."},
    "toilet": {"asset_id": 102677, "class": "ToiletRLEnv", "instruction":
               "Use the Allegro hand to lift and open the toilet lid fully."},
}

# Fixed mounting positions, chosen before episodes; never computed from object state.
CAMERA_PRESETS = {
    "faucet": {"front": ((-0.30, 0.65, 0.45), (-0.20, 0.20, 0.16)),
               "oblique": ((0.25, -0.30, 0.45), (-0.20, 0.20, 0.16))},
    "laptop": {"front": ((0.10, 0.75, 0.50), (0.10, 0., 0.22)),
               "oblique": ((0.65, -0.50, 0.60), (0.05, 0., 0.22))},
    "bucket": {"front": ((-0.20, 0.75, 0.65), (-0.10, 0., 0.30)),
               "oblique": ((0.50, -0.55, 0.65), (-0.10, 0., 0.30))},
    "toilet": {"front": ((0., 0.70, 0.75), (0., -0.10, 0.40)),
               "oblique": ((-0.65, 0.55, 0.75), (0., -0.10, 0.40))},
}


def camera_rotation(position, look_at):
    """SAPIEN camera local axes are forward +X, left +Y, up +Z."""
    forward = np.asarray(look_at, dtype=float) - np.asarray(position, dtype=float)
    forward /= np.linalg.norm(forward)
    left = np.cross([0., 0., 1.], forward)
    left /= np.linalg.norm(left)
    up = np.cross(forward, left)
    return np.column_stack((forward, left, up))


def robot_proprioception(env):
    """Allowlist: articulation encoders and robot-link FK, no native obs dictionary."""
    pose = env.palm_link.get_pose()
    matrix = pose.to_transformation_matrix()
    ee_pose = env.ee_link.get_pose()
    return {"joint_positions": env.robot.get_qpos().copy().tolist(),
            "joint_velocities": env.robot.get_qvel().copy().tolist(),
            "palm_position_world": np.asarray(pose.p).copy().tolist(),
            "palm_rotation_world_rowmajor": matrix[:3, :3].reshape(-1).tolist(),
            "controller_link_position_world": np.asarray(ee_pose.p).copy().tolist(),
            "controller_link_rotation_world_rowmajor": ee_pose.to_transformation_matrix()[:3, :3].reshape(-1).tolist()}


def build_action_spec(env, task, asset_id):
    joints = [joint.get_name() for joint in env.robot.get_active_joints()]
    limits = np.asarray(env.robot.get_qlimits(), dtype=float)
    if env.robot.dof != 22 or env.arm_dof != 6 or len(joints) != 22:
        raise ValueError("Expected native xArm6 + 16-DOF Allegro configuration")
    if not np.isfinite(limits[6:]).all() or np.any(limits[6:, 0] >= limits[6:, 1]):
        raise ValueError("Finger joint limits must be finite increasing ranges")
    velocity = np.asarray(env.velocity_limit[:6], dtype=float)
    if not np.allclose(env.robot.get_pose().to_transformation_matrix()[:3, :3], np.eye(3), atol=1e-6):
        raise ValueError("This action documentation requires the benchmark's identity base rotation")
    return {
        "spec_version": "dexart-native-cartesian-allegro-v1", "task": "dexart_" + task,
        "simulator": "SAPIEN / PhysX (DexArt)", "robot": ROBOT_NAME,
        "asset_id": asset_id, "asset_split": "seen", "dimension": 22,
        "names": ["wrist_vx", "wrist_vy", "wrist_vz", "wrist_wx", "wrist_wy", "wrist_wz"] + joints[6:],
        "low": [-1.] * 22, "high": [1.] * 22,
        "control_dt": float(env.control_time_step), "native_horizon_steps": int(env.horizon),
        "joint_names": joints, "joint_units": ["radians"] * 22,
        "joint_position_indices": list(range(22)), "joint_velocity_indices": list(range(22)),
        "finger_target_ranges_rad": limits[6:].tolist(),
        "wrist_velocity_ranges": velocity.tolist(),
        "robot_base_position_world": env.robot.get_pose().p.tolist(),
        "robot_base_rotation_world_rowmajor": env.robot.get_pose().to_transformation_matrix()[:3, :3].reshape(-1).tolist(),
        "palm_fk_link_name": env.palm_link.get_name(), "controller_fk_link_name": env.ee_link.get_name(),
        "finger_groups": {finger: [6 + joints[6:].index(f"joint_{joint}.0") for joint in range(start, start + 4)]
                          for finger, start in (("index", 0), ("middle", 4), ("ring", 8), ("thumb", 12))},
        "semantics": (
            "Native DexArt 22-dimensional controller. Actions 0..5 are desired wrist spatial VELOCITIES "
            "(vx,vy,vz in meters/second; wx,wy,wz in radians/second), affine mapped from [-1,1] "
            "to wrist_velocity_ranges. The native partial-arm Jacobian uses axes aligned with the "
            "robot base; this benchmark mounts the base with identity world rotation, so +X,+Y,+Z "
            "are world axes and +Z is up. Angular velocities follow the right-hand rule. "
            "Native damped inverse kinematics maps this twist into six arm-joint velocities, "
            "clips them to +/-pi rad/s, and integrates one control_dt into arm joint drive targets. "
            "Actions 6..21 are absolute finger JOINT POSITION TARGETS: q_target=low+(action+1)/2*(high-low), "
            "using finger_target_ranges_rad in the listed joint order. They are not torques or velocities. "
            "Allegro has index, middle, ring and thumb, no little finger: finger_groups lists action "
            "indices by anatomical digit. joint_0/4/8 are nonthumb base spread joints; the next three "
            "joints in each digit run from proximal to distal. joint_12..15 form the thumb chain. "
            "A larger normalized finger action always increases that joint coordinate; the URDF "
            "joint-local axes and positive right-hand rotation are documented in finger_joint_geometry. "
            "To hold fingers at measured q, action=2*(q-low)/(high-low)-1 (bounded [-1,1]). "
            "Zero wrist controls request zero Cartesian motion; zero finger controls request joint-range "
            "midpoints, NOT an open hand or hold. Native PD drives and passive-force compensation apply; "
            "contacts, joint limits, and IK error can prevent requested motion. No grasp controller or "
            "scripted task trajectory is added. Proprioception lists all six arm plus sixteen finger "
            "encoder positions and velocities; palm pose is robot FK. repeat repeats this native action "
            "for that many simulation control steps; done=true stops without executing the action. "
            "Only fixed-camera RGB and robot proprioception are policy observations."
        ),
    }


class DexArtTaskEnvironment:
    def __init__(self, task, instruction=None, dataset_path=None, max_steps=250, image_size=768,
                 source_path=None, seed=0, device=""):
        task = task.removeprefix("dexart_")
        if task not in DEXART_TASKS:
            raise ValueError(f"Unknown DexArt task {task!r}")
        if dataset_path is not None:
            raise ValueError("DexArt resets use the benchmark asset dataset, not an episode replay path")
        if max_steps < 1 or image_size < 1:
            raise ValueError("Step budget and image size must be positive")
        source = Path(source_path) if source_path else Path(__file__).resolve().parents[2] / "data/dexart/source"
        if source.is_dir() and str(source.resolve()) not in sys.path:
            sys.path.insert(0, str(source.resolve()))
        import sapien.core as sapien
        from transforms3d.quaternions import mat2quat
        from dexart.env.task_setting import TASK_CONFIG, TRAIN_CONFIG
        from dexart.env.sim_env.constructor import add_default_scene_light
        upstream = getattr(importlib.import_module(f"dexart.env.rl_env.{task}_env"), DEXART_TASKS[task]["class"])

        class SensorOnlyNativeEnvironment(upstream):
            def get_oracle_state(self):
                # Called during upstream construction/reset; never assemble privileged observations.
                return {}

        self.task, self.step_index = task, 0
        self.instruction = instruction or DEXART_TASKS[task]["instruction"]
        self.asset_id = DEXART_TASKS[task]["asset_id"]
        if self.asset_id not in TRAIN_CONFIG[task]["seen"]:
            raise ValueError("Predetermined asset must belong to the documented seen split")
        random.seed(seed)
        np.random.seed(seed)
        self.env = SensorOnlyNativeEnvironment(
            use_gui=False, frame_skip=10, robot_name=ROBOT_NAME,
            index=TASK_CONFIG[task].index(self.asset_id), rand_pos=0., rand_orn=0.,
            use_visual_obs=False, no_rgb=False, need_offscreen_render=True, device=device)
        self.env.seed(seed)
        self.max_steps = min(int(max_steps), int(self.env.horizon))
        add_default_scene_light(self.env.scene, self.env.renderer)
        self._cameras = {}
        calibration = {}
        fovy = float(np.deg2rad(69.4))
        for name, (position, look_at) in CAMERA_PRESETS[task].items():
            rotation = camera_rotation(position, look_at)
            camera = self.env.scene.add_camera(name, width=image_size, height=image_size,
                                               fovy=fovy, near=0.01, far=5.)
            camera.set_local_pose(sapien.Pose(position, mat2quat(rotation)))
            self._cameras[name] = camera
            focal = image_size / (2 * np.tan(fovy / 2))
            calibration[name] = {
                "width": image_size, "height": image_size, "position_world": list(position),
                "forward_world": rotation[:, 0].tolist(), "up_world": rotation[:, 2].tolist(),
                "intrinsics_fx_fy_cx_cy": [float(focal), float(focal), image_size / 2, image_size / 2],
                "projection": "perspective; pixel x right/y down; fixed scene-independent mount; no distortion"}
        self.action_spec = build_action_spec(self.env, task, self.asset_id)
        self.action_spec["camera_calibration"] = calibration
        urdf = ET.parse(source / "assets" / self.env.robot_info.path)
        geometry = {}
        for joint in urdf.getroot().findall("joint"):
            if joint.attrib.get("name") not in self.action_spec["joint_names"][6:]:
                continue
            axis = joint.find("axis")
            geometry[joint.attrib["name"]] = {"axis_in_urdf_joint_frame":
                [float(value) for value in axis.attrib["xyz"].split()],
                "positive_direction": "right-hand rotation about this joint-local axis"}
        self.action_spec["finger_joint_geometry"] = geometry
        versions = {}
        for package in ("sapien", "numpy", "gym", "open3d"):
            try:
                versions[package] = version(package)
            except PackageNotFoundError:
                versions[package] = "unreported"
        revision = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, timeout=5)
        self.action_spec["provenance"] = {
            "source_repository": "https://github.com/Kami-code/dexart-release",
            "source_commit": revision.stdout.strip() if revision.returncode == 0 else None,
            "package_versions": versions, "initialization": "fixed seen asset; native reset; rand_pos=0; rand_orn=0",
            "construction_seed": seed, "native_frame_skip": 10}

    def _observation(self):
        self.env.scene.update_render()
        images = {}
        for name, camera in self._cameras.items():
            camera.take_picture()
            rgb = camera.get_float_texture("Color")[..., :3]
            images[name] = (np.clip(rgb, 0., 1.) * 255).astype(np.uint8)
        return Observation(images=images, proprioception=robot_proprioception(self.env),
                           instruction=self.instruction, step_index=self.step_index)

    def reset(self, seed=0, episode_id=None):
        if episode_id is not None:
            raise ValueError("DexArt uses a predetermined asset and native reset, not demonstration episode IDs")
        random.seed(seed)
        np.random.seed(seed)
        self.env.seed(seed)
        self.env.reset(seed=seed)
        self.step_index = 0
        if int(self.env.index) != self.asset_id:
            raise RuntimeError("Native environment changed the predetermined asset")
        return self._observation()

    def step(self, action):
        action = np.asarray(action, dtype=np.float64)
        if action.shape != (22,) or not np.isfinite(action).all() or np.any(np.abs(action) > 1):
            raise ValueError("DexArt requires exactly 22 finite controls in [-1,1]")
        # Native control and success evaluation, without collecting any native observation.
        self.env.rl_step(action)
        self.env.update_cached_state()
        self.step_index += 1
        evaluation = {"success": bool(self.env.is_eval_done),
                      "reward": float(self.env.get_reward(action)),
                      "native_evaluation": "is_eval_done"}
        for field in ("openness", "progress", "delta_height", "is_contact", "state"):
            value = getattr(self.env, field, None)
            if value is not None and np.isscalar(value):
                evaluation[field] = float(value)
        terminal = bool(self.env.is_done() or self.step_index >= self.max_steps)
        return self._observation(), terminal, evaluation

    def close(self):
        if getattr(self, "env", None) is None:
            return
        if self.env.viewer is not None:
            self.env.viewer.close()
        self._cameras.clear()
        self.env.scene = None
        self.env = None


DexArtEnvironment = DexArtTaskEnvironment

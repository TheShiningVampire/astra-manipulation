"""PyBullet comparison: native Panda Cartesian control with image-only task sensing."""
from __future__ import annotations

from importlib.metadata import version
import numpy as np

from .core import Observation

BULLET_TASKS = {
    "bullet_reach": {"env_id": "PandaReach-v3", "instruction": "Move the closed gripper's tip into the magenta target sphere."},
    "bullet_pick_place": {"env_id": "PandaPickAndPlace-v3", "instruction": "Grasp the solid green cube and carry its center to the magenta target cube."},
}


class BulletTaskEnvironment:
    def __init__(self, task, instruction=None, dataset_path=None, max_steps=600, image_size=768):
        import gymnasium as gym
        import panda_gym  # noqa: F401: registers benchmark environments
        import pybullet
        if task not in BULLET_TASKS:
            raise ValueError(f"Unknown Bullet task {task!r}")
        if dataset_path is not None:
            raise ValueError("PyBullet comparison uses seeded benchmark resets, not recorded dataset episodes")
        self.task = task
        self.instruction = instruction or BULLET_TASKS[task]["instruction"]
        self.step_index = 0
        self.env = gym.make(BULLET_TASKS[task]["env_id"], render_mode="rgb_array", renderer="Tiny",
                            control_type="ee", max_episode_steps=max_steps)
        self._u = self.env.unwrapped
        self._robot, self._sim = self._u.robot, self._u.sim
        self._client, self._pb = self._sim.physics_client, pybullet
        self._robot_body = self._sim._bodies_idx[self._robot.body_name]
        self._joints = tuple(int(j) for j in self._robot.joint_indices)
        self._image_size = image_size
        # Visual styling only: same target pose, collision settings and success predicate.
        # Opaque magenta is discernible on Tiny Renderer without relying on transparency.
        self._client.changeVisualShape(self._sim._bodies_idx["target"], -1, rgbaColor=[0.9,0.05,0.65,1.0])
        self._camera_matrices = {}
        cameras = {}
        for name, yaw, pitch in (("front",45,-35),("overhead_oblique",-55,-60)):
            view = self._client.computeViewMatrixFromYawPitchRoll(
                cameraTargetPosition=[-0.10,0,0.10], distance=1.05, yaw=yaw,pitch=pitch,roll=0,upAxisIndex=2)
            projection = self._client.computeProjectionMatrixFOV(fov=60,aspect=1,nearVal=.05,farVal=10)
            self._camera_matrices[name] = (view,projection)
            camera_to_world = np.linalg.inv(np.array(view).reshape(4,4,order="F"))
            focal = image_size/(2*np.tan(np.deg2rad(30)))
            cameras[name] = {"width":image_size,"height":image_size,
                "position_world":camera_to_world[:3,3].tolist(),
                "forward_world":(-camera_to_world[:3,2]).tolist(),"up_world":camera_to_world[:3,1].tolist(),
                "intrinsics_fx_fy_cx_cy":[float(focal),float(focal),image_size/2,image_size/2],
                "view_matrix_opengl_columnmajor":list(view),"projection_matrix_opengl_columnmajor":list(projection),
                "projection":"fixed world perspective, pixel x right y down, no distortion"}
        action_names = ["world_delta_x","world_delta_y","world_delta_z"]
        if not self._robot.block_gripper:
            action_names.append("finger_width_delta")
        self.action_spec = {
            "spec_version":"pybullet-cartesian-v1", "task":task,"names":action_names,
            "dimension":len(action_names),"low":self.env.action_space.low.tolist(),"high":self.env.action_space.high.tolist(),
            "control_dt":float(self._sim.dt),"position_delta_scale_m":.05,"finger_width_delta_scale_m":.2,
            "proprioception_joint_names":[self._client.getJointInfo(self._robot_body,j)[1].decode() for j in self._joints],
            "proprioception_joint_indices":list(self._joints),"camera_calibration":cameras,
            "versions":{"panda_gym":version("panda-gym"),"pybullet":version("pybullet")},
            "semantics":"Native Panda Cartesian displacement control. Each step commands current measured end-effector XYZ + 0.05*action[:3] meters in WORLD coordinates. +Z goes UP. Downward gripper orientation is held by inverse kinematics, quaternion xyzw=[1,0,0,0]; orientation is not controllable. Target Z is clipped to >=0. Last action (only if present) changes total finger width by 0.2*action meters: POSITIVE OPENS, NEGATIVE CLOSES, ZERO targets current width. Robot joint limits constrain actual opening. Zero XYZ requests current measured pose. Actions are positional increments, not velocities; repeating an action re-applies the increment at each 0.04s control step. Motor dynamics mean measured displacement can differ. Reach has only three actions and a blocked closed gripper; PickAndPlace has four. Magenta target is a visible noncolliding marker; green solid cube is manipulable. The robot measurements and calibrated RGB are the only task sensing.",
            "command_protocol":"done=true stops IMMEDIATELY and discards the action in that same response: no movement or gripper command is executed. Keep done=false while issuing any motion, including the final approach. Native success terminates the environment automatically. repeat is the count of incremental control steps, so large repeats can overshoot.",
        }

    def _observation(self):
        images = {}
        for name,(view,projection) in self._camera_matrices.items():
            rgba = self._client.getCameraImage(self._image_size,self._image_size,viewMatrix=view,
                    projectionMatrix=projection,renderer=self._pb.ER_TINY_RENDERER,shadow=1)[2]
            images[name] = np.asarray(rgba,dtype=np.uint8).reshape(self._image_size,self._image_size,4)[:,:,:3].copy()
        # Explicit robot API calls: never native task observation, achieved_goal or desired_goal.
        proprio = {
            "joint_positions":[float(self._robot.get_joint_angle(j)) for j in self._joints],
            "joint_velocities":[float(self._robot.get_joint_velocity(j)) for j in self._joints],
            "eef_position_world":self._robot.get_ee_position().tolist(),
            "eef_velocity_world":self._robot.get_ee_velocity().tolist(),
            "eef_orientation_xyzw":self._sim.get_link_orientation(self._robot.body_name,self._robot.ee_link).tolist(),
            "finger_width_m":[float(self._robot.get_fingers_width())],
        }
        return Observation(images=images,proprioception=proprio,instruction=self.instruction,step_index=self.step_index)

    def reset(self, seed=0, episode_id=None):
        if episode_id is not None:
            raise ValueError("PyBullet uses seeded resets, not recorded dataset episode indices")
        self.step_index = 0
        self.env.reset(seed=seed)
        return self._observation()

    def step(self, action):
        _,reward,terminated,truncated,info = self.env.step(np.asarray(action,dtype=np.float32))
        self.step_index += 1
        # Privileged evaluation is deliberately separate from Observation.
        achieved = self._u.task.get_achieved_goal()
        goal = self._u.task.get_goal()
        metrics = {"success":bool(info["is_success"]),"reward":float(reward),
                   "goal_distance_m":float(np.linalg.norm(achieved-goal))}
        if self.task == "bullet_pick_place":
            metrics["object_height_m"] = float(achieved[2])
        return self._observation(),bool(terminated or truncated),metrics

    def close(self):
        self.env.close()

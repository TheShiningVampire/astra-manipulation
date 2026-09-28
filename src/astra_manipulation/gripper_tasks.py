"""Five native robosuite tasks with a camera / robot-encoder observation boundary."""
import json
import os
import xml.etree.ElementTree as ET

import numpy as np

from .environments import LiftEnvironment


GRIPPER_TASKS = {
    "lift": {"env_name": "Lift", "instruction": "Grasp the small red cube with the gripper and lift it clearly above the table. Keep holding it above the table."},
    "stack": {"env_name": "Stack", "instruction": "Pick up the small red cube, place it on top of the larger green cube, release it, and move the gripper away. Leave the red cube resting on the green cube."},
    "door": {"env_name": "Door", "instruction": "Grasp the door handle and pull the hinged door open by at least about 20 degrees. Leave the door open."},
    "nut_assembly_square": {"env_name": "NutAssemblySquare", "instruction": "Grasp the square nut by its protruding handle. Fit its square hole over the square peg on the table, lower it onto the peg, then release and move the gripper away."},
    "pick_place_can": {"env_name": "PickPlaceCan", "instruction": "Pick up the red can from the source bin and place it inside the compartment outlined by the bright green rectangular frame in the other bin. Release the can and move the gripper away. The green frame is a visible destination marker."},
}


class GripperTaskEnvironment(LiftEnvironment):
    def __init__(self, task, instruction=None, dataset_path=None, max_steps=600, image_size=512):
        aliases = {v["env_name"].lower(): k for k, v in GRIPPER_TASKS.items()}
        task = aliases.get(task.lower(), task.lower())
        if task not in GRIPPER_TASKS:
            raise ValueError(f"Unknown gripper task: {task}")
        if dataset_path and task != "lift":
            raise ValueError("Recorded dataset resets are supported only for Lift")
        if image_size < 64 or max_steps < 1:
            raise ValueError("image_size must be >=64 and max_steps positive")
        os.environ.setdefault("MUJOCO_GL", "egl")
        import robosuite
        from robosuite.controllers import load_part_controller_config
        from robosuite.controllers.composite.composite_controller_factory import refactor_composite_controller_config

        self.task = task
        self.instruction = instruction or GRIPPER_TASKS[task]["instruction"]
        self.dataset_path, self.max_steps, self.step_index = dataset_path, max_steps, 0
        kwargs = {}
        if dataset_path:
            import h5py
            with h5py.File(dataset_path, "r") as data:
                metadata = json.loads(data["data"].attrs["env_args"])
            if metadata["env_name"] != "Lift":
                raise ValueError("Expected a Lift dataset")
            kwargs.update(metadata["env_kwargs"])
        controller = load_part_controller_config(default_controller="OSC_POSE")
        # Explicit configuration: match the action description to controller execution.
        controller.update(input_type="delta", input_ref_frame="base",
                          output_max=[0.05, 0.05, 0.05, 0.5, 0.5, 0.5],
                          output_min=[-0.05, -0.05, -0.05, -0.5, -0.5, -0.5])
        kwargs.update(robots="Panda", has_renderer=False, has_offscreen_renderer=True,
                      use_camera_obs=True, use_object_obs=False,
                      camera_names=["agentview", "robot0_eye_in_hand"],
                      camera_heights=image_size, camera_widths=image_size, camera_depths=False,
                      reward_shaping=False, horizon=max_steps, ignore_done=False, control_freq=20,
                      controller_configs=refactor_composite_controller_config(controller, "Panda", ["right"]))
        if task == "pick_place_can":
            from robosuite.environments.manipulation.pick_place import PickPlaceCan

            class VisibleDestinationCan(PickPlaceCan):
                def _load_model(inner):
                    super()._load_model()
                    # Can is bin index 3: +X,+Y quadrant. Static task fixture,
                    # never tracks an object or exposes simulator state in text.
                    center = inner.bin2_pos.copy()
                    center[:2] += inner.bin_size[:2] / 4
                    # Bin floor box has 0.02 m half-height; sit just above it.
                    center[2] += 0.024
                    half = inner.bin_size[:2] / 4 - 0.008
                    for axis in (0, 1):
                        for sign in (-1, 1):
                            position = center.copy()
                            position[axis] += sign * half[axis]
                            size = [half[0], half[1], 0.002]
                            size[axis] = 0.003
                            inner.model.worldbody.append(ET.Element("geom", {
                                "name": f"visible_can_goal_{axis}_{sign}", "type": "box",
                                "pos": " ".join(map(str, position)), "size": " ".join(map(str, size)),
                                "rgba": "0 1 0 1", "contype": "0", "conaffinity": "0", "group": "1"}))
            self.env = VisibleDestinationCan(**kwargs)
        else:
            self.env = robosuite.make(GRIPPER_TASKS[task]["env_name"], **kwargs)
        low, high = self.env.action_spec
        if len(low) != 7:
            self.env.close()
            raise RuntimeError("Expected six pose deltas plus one gripper command")
        self.action_spec = {
            "names": ["delta_x", "delta_y", "delta_z", "delta_rx", "delta_ry", "delta_rz", "gripper"],
            "low": low.tolist(), "high": high.tolist(), "dimension": 7,
            "control_dt": 1 / self.env.control_freq,
            "semantics": "Normalized robot BASE-frame end-effector pose DELTAS, not absolute positions. Translation scale 0.05 meters; rotation scale 0.5 radians. Gripper -1 opens, +1 closes. One command advances one control interval. Encoder/FK-derived eef_pos is the gripper site WORLD position; eef_quat is the end-effector BODY WORLD quaternion in xyzw order (body and site frames can differ). Camera images provide all object and target information.",
        }

    def reset(self, seed, episode_id=None):
        if episode_id is not None and self.task != "lift":
            raise ValueError("Only Lift supports recorded episode resets; other tasks use seeded native resets")
        observation = super().reset(seed=seed, episode_id=episode_id)
        if self.task in {"door", "pick_place_can"}:
            camera = self.env.sim.model.camera_name2id("agentview")
            # Fixed camera calibration for the full workspace, independent of
            # object state. The native Door camera crops most of its handle.
            if self.task == "door":
                self.env.sim.model.cam_pos[camera] = [0.85, -0.35, 1.69]
            self.env.sim.model.cam_fovy[camera] = 55
            self.env.sim.forward()
            observation = self._observation(self.env._get_observations(force_update=True))
        return observation

    def step(self, action):
        observation, done, metrics = super().step(action)
        # Native diagnostics stay in evaluator output, never robot proprioception.
        metrics["task"] = self.task
        if self.task == "door":
            metrics["door_hinge_radians"] = float(self.env.sim.data.qpos[self.env.hinge_qpos_addr])
        elif self.task == "pick_place_can":
            metrics["can_in_destination"] = bool(self.env.objects_in_bins[self.env.object_id])
        return observation, done, metrics

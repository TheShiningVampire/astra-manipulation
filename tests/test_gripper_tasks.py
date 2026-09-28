from types import SimpleNamespace

import numpy as np
import pytest

from astra_manipulation.gripper_tasks import GRIPPER_TASKS, GripperTaskEnvironment


def test_task_catalog_has_five_distinct_native_tasks():
    assert len(GRIPPER_TASKS) == 5
    assert len({v["env_name"] for v in GRIPPER_TASKS.values()}) == 5
    assert "green" in GRIPPER_TASKS["pick_place_can"]["instruction"]


def test_reject_nonlift_dataset_before_simulator_creation():
    with pytest.raises(ValueError, match="only for Lift"):
        GripperTaskEnvironment("stack", dataset_path="not-a-real-file.hdf5")


def test_robot_observation_whitelist_excludes_task_state():
    wrapper = object.__new__(GripperTaskEnvironment)
    wrapper.instruction, wrapper.step_index = "Open the door", 0
    raw = {"robot0_joint_pos": np.zeros(7), "robot0_eef_pos": np.ones(3),
           "door_pos": np.ones(3), "hinge_qpos": np.array([0.7]),
           "robot0_proprio-state": np.ones(100), "object-state": np.ones(30),
           "agentview_image": np.zeros((16, 16, 3), dtype=np.uint8),
           "robot0_eye_in_hand_image": np.zeros((16, 16, 3), dtype=np.uint8)}
    obs = wrapper._observation(raw)
    assert set(obs.proprioception) == {"robot0_joint_pos", "robot0_eef_pos"}
    assert set(obs.images) == {"agentview", "robot0_eye_in_hand"}


def test_seed_is_applied_to_native_simulator_reset():
    wrapper = object.__new__(GripperTaskEnvironment)
    wrapper.task, wrapper.step_index = "stack", 99
    wrapper._observation = lambda raw: raw
    wrapper.env = SimpleNamespace(reset=lambda: "observation")
    assert wrapper.reset(42) == "observation"
    assert wrapper.step_index == 0
    assert wrapper.env.seed == 42
    assert wrapper.env.rng.random() == np.random.default_rng(42).random()
    with pytest.raises(ValueError, match="Only Lift"):
        wrapper.reset(42, episode_id=0)

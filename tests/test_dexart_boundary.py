from types import SimpleNamespace

import numpy as np

from astra_manipulation.dexart_tasks import camera_rotation, robot_proprioception


def test_robot_proprioception_does_not_access_task_state_or_oracle():
    class RobotOnlyEnv:
        robot = SimpleNamespace(get_qpos=lambda: np.zeros(22), get_qvel=lambda: np.ones(22))
        palm_link = SimpleNamespace(get_pose=lambda: SimpleNamespace(
            p=np.array([1., 2., 3.]), to_transformation_matrix=lambda: np.eye(4)))
        ee_link = SimpleNamespace(get_pose=lambda: SimpleNamespace(
            p=np.array([4., 5., 6.]), to_transformation_matrix=lambda: np.eye(4)))

        def __getattr__(self, name):
            raise AssertionError("Unexpected state access: " + name)

    state = robot_proprioception(RobotOnlyEnv())
    assert set(state) == {"joint_positions", "joint_velocities", "palm_position_world",
                          "palm_rotation_world_rowmajor", "controller_link_position_world",
                          "controller_link_rotation_world_rowmajor"}
    assert len(state["joint_positions"]) == 22
    assert state["palm_position_world"] == [1., 2., 3.]
    assert state["controller_link_position_world"] == [4., 5., 6.]


def test_fixed_camera_rotation_is_right_handed_and_looks_at_target():
    position, target = np.array([-.3, .9, .8]), np.array([-.1, .1, .3])
    rotation = camera_rotation(position, target)
    np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
    np.testing.assert_allclose(np.linalg.det(rotation), 1, atol=1e-12)
    np.testing.assert_allclose(rotation[:, 0], (target-position)/np.linalg.norm(target-position))

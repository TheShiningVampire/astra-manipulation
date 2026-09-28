from types import SimpleNamespace

import numpy as np
import pytest

from astra_manipulation.dexart_tasks import CAMERA_PRESETS, build_action_spec, camera_rotation


def test_all_fixed_camera_frames_are_right_handed_and_look_at_static_target():
    for cameras in CAMERA_PRESETS.values():
        assert set(cameras) == {"front", "oblique"}
        for position, target in cameras.values():
            rotation = camera_rotation(position, target)
            np.testing.assert_allclose(rotation.T @ rotation, np.eye(3), atol=1e-12)
            assert np.linalg.det(rotation) == pytest.approx(1.)
            direction = np.subtract(target, position)
            np.testing.assert_allclose(rotation[:, 0], direction / np.linalg.norm(direction))


def test_native_spec_maps_all_fingers_without_assuming_articulation_order():
    # Different articulation ordering still maps anatomy by verified joint names.
    names = [f"arm{i}" for i in range(6)] + [f"joint_{i}.0" for i in reversed(range(16))]
    pose = SimpleNamespace(p=np.zeros(3), to_transformation_matrix=lambda: np.eye(4))
    robot = SimpleNamespace(dof=22, get_pose=lambda: pose,
        get_active_joints=lambda: [SimpleNamespace(get_name=lambda name=name: name) for name in names],
        get_qlimits=lambda: np.tile([-1., 1.], (22, 1)))
    env = SimpleNamespace(robot=robot, arm_dof=6, velocity_limit=np.tile([-1., 1.], (22, 1)),
                          control_time_step=.04, horizon=250,
                          palm_link=SimpleNamespace(get_name=lambda: "base_link"),
                          ee_link=SimpleNamespace(get_name=lambda: "link6"))
    spec = build_action_spec(env, "faucet", 148)
    assert spec["dimension"] == 22
    assert spec["finger_groups"]["index"] == [21, 20, 19, 18]
    assert spec["finger_groups"]["thumb"] == [9, 8, 7, 6]
    assert sorted(sum(spec["finger_groups"].values(), [])) == list(range(6, 22))
    robot.dof = 23
    with pytest.raises(ValueError, match="configuration"):
        build_action_spec(env, "faucet", 148)

import numpy as np
import pytest

from astra_manipulation.bullet_tasks import BulletTaskEnvironment


@pytest.fixture(params=["bullet_reach","bullet_pick_place"])
def env(request):
    pytest.importorskip("panda_gym")
    instance = BulletTaskEnvironment(request.param,max_steps=3,image_size=48)
    yield instance
    instance.close()


def test_robot_sensors_do_not_access_task_goals_or_native_observation(env,monkeypatch):
    env.reset(0)
    def forbidden(*args,**kwargs):
        raise AssertionError("Policy observation accessed privileged task state")
    monkeypatch.setattr(env._u,"_get_obs",forbidden)
    monkeypatch.setattr(env._u.task,"get_obs",forbidden)
    monkeypatch.setattr(env._u.task,"get_goal",forbidden)
    monkeypatch.setattr(env._u.task,"get_achieved_goal",forbidden)
    obs = env._observation()
    assert set(obs.proprioception) == {"joint_positions","joint_velocities","eef_position_world",
                                       "eef_velocity_world","eef_orientation_xyzw","finger_width_m"}
    assert len(obs.proprioception["joint_positions"]) == 9
    assert all(frame.shape == (48,48,3) for frame in obs.images.values())


def test_native_cartesian_mapping_and_protocol(env,monkeypatch):
    env.reset(0)
    measured = env._robot.get_ee_position()
    captured = {}
    def ik(**kwargs):
        captured.update(kwargs)
        return np.zeros(9)
    monkeypatch.setattr(env._robot,"inverse_kinematics",ik)
    env._robot.ee_displacement_to_target_arm_angles(np.array([.2,-.3,.4]))
    np.testing.assert_allclose(captured["position"],measured+np.array([.01,-.015,.02]))
    np.testing.assert_array_equal(captured["orientation"],[1,0,0,0])
    assert env.action_spec["control_dt"] == .04
    assert "discards the action" in env.action_spec["command_protocol"]
    assert "POSITIVE OPENS" in env.action_spec["semantics"]
    assert env.action_spec["dimension"] == (3 if env.task == "bullet_reach" else 4)


def test_calibration_static_across_resets_and_episode_rejected(env):
    before = repr(env.action_spec["camera_calibration"])
    env.reset(0)
    env.reset(3)
    assert before == repr(env.action_spec["camera_calibration"])
    with pytest.raises(ValueError,match="seeded"):
        env.reset(0,episode_id=0)

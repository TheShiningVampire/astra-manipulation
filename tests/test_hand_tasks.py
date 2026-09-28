from types import SimpleNamespace

import numpy as np
import pytest

from astra_manipulation.hand_tasks import HAND_TASKS, HandTaskEnvironment, robot_actuator_mapping


@pytest.mark.parametrize("task,count", [("relocate",30),("door",28),("hammer",26),("pen",24),("ball_lift",30)])
def test_actual_robot_joint_mapping(task, count):
    gym = pytest.importorskip("gymnasium")
    robotics = pytest.importorskip("gymnasium_robotics")
    mujoco = pytest.importorskip("mujoco")
    gym.register_envs(robotics)
    env = gym.make(HAND_TASKS[task]["env_id"])
    try:
        model = env.unwrapped.model
        names, joints = robot_actuator_mapping(model, mujoco)
        assert len(names) == len(joints) == count
        for name, joint in zip(names, joints):
            assert name[2:] == mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_JOINT, int(joint))
        assert len(set(model.jnt_qposadr[joints])) == count
        # Every model includes nonrobot object joints beyond the actuated robot.
        assert len(joints) < model.njnt
    finally:
        env.close()


def test_observation_uses_resolved_addresses_not_state_prefix():
    adapter = HandTaskEnvironment.__new__(HandTaskEnvironment)
    data = SimpleNamespace(qpos=np.array([9999, .1, 9999, .2]), qvel=np.array([9999, .3, 9999, .4]),
                           site_xpos=np.array([[9999]*3,[.1,.2,.3]]),
                           site_xmat=np.array([[9999]*9,np.eye(3).reshape(-1)]))
    adapter._u = SimpleNamespace(data=data)
    adapter._qpos = adapter._qvel = np.array([1,3])
    adapter._palm = 1
    adapter._cameras = {"front": object()}
    adapter._renderer = SimpleNamespace(update_scene=lambda *args, **kwargs: None,
                                       render=lambda: np.zeros((4,4,3),dtype=np.uint8))
    adapter.instruction, adapter.step_index = "Task", 0
    obs = adapter._observation()
    assert obs.proprioception["joint_positions"] == [.1,.2]
    assert obs.proprioception["joint_velocities"] == [.3,.4]
    assert "9999" not in str(obs.text())


def test_ball_lift_requires_five_consecutive_height_steps_and_resets():
    adapter = HandTaskEnvironment.__new__(HandTaskEnvironment)
    adapter.task, adapter.step_index, adapter._height_hold = "ball_lift",0,0
    data = SimpleNamespace(xpos=np.array([[0.,0.,.11]]),site_xpos=np.array([[0.,0.,.2]]))
    adapter._u = SimpleNamespace(data=data,obj_body_id=0)
    adapter._palm = 0
    adapter.env = SimpleNamespace(step=lambda action: (None,123,False,False,{"success":True}))
    adapter._observation = lambda: None
    for _ in range(4):
        assert not adapter.step([])[2]["success"]
    assert adapter.step([])[2]["success"]
    data.xpos[0,2] = .10
    assert not adapter.step([])[2]["success"]
    assert adapter._height_hold == 0

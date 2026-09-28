"""Check policy-visible sensor boundaries without running expensive simulation."""
import pickle
import io
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from astra_manipulation.environments import AdroitEnvironment, LiftEnvironment
from astra_manipulation.datasets import _NumericNumpyUnpickler


def test_adroit_never_exposes_privileged_object_goal_channels():
    adapter = AdroitEnvironment.__new__(AdroitEnvironment)
    adapter.instruction, adapter.step_index = "Move the ball", 4
    frame = np.full((3, 4, 3), 127, dtype=np.uint8)
    adapter.env = SimpleNamespace(render=lambda: frame)
    raw = np.concatenate([np.arange(30), np.full(9, 991234.0)])
    observation = adapter._observation(raw)
    assert observation.proprioception == {"joint_positions": list(range(30))}
    raw[:30] = -999
    frame[:] = 0
    assert observation.proprioception["joint_positions"][0] == 0
    assert np.all(observation.images["external"] == 127)
    assert "991234" not in str(observation.text())


def test_lift_whitelist_excludes_objects_composites_rewards_and_info(monkeypatch):
    monkeypatch.setitem(sys.modules, "robosuite", SimpleNamespace(
        macros=SimpleNamespace(IMAGE_CONVENTION="opengl")))
    adapter = LiftEnvironment.__new__(LiftEnvironment)
    adapter.instruction, adapter.step_index = "Lift the cube", 0
    frame = np.arange(18, dtype=np.uint8).reshape(2, 3, 3)
    raw = {"robot0_joint_pos": np.array([0.1, 0.2]), "cube_pos": np.array([991234.0]),
           "object-state": np.array([991234.0]), "robot0_proprio-state": np.array([991234.0]),
           "success": True, "reward": 991234.0,
           "agentview_image": frame, "robot0_eye_in_hand_image": frame}
    observation = adapter._observation(raw)
    assert observation.proprioception == {"robot0_joint_pos": [0.1, 0.2]}
    np.testing.assert_array_equal(observation.images["agentview"], frame[::-1])
    assert "991234" not in str(observation.text())


def test_restricted_dataset_loader_rejects_executable_globals():
    # Pickling a builtin does not execute it; restricted loading must reject it.
    payload = pickle.dumps(eval)
    with pytest.raises(pickle.UnpicklingError, match="Disallowed"):
        _NumericNumpyUnpickler(io.BytesIO(payload)).load()

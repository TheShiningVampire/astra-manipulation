import json
from types import SimpleNamespace

import numpy as np
import pytest

from astra_manipulation.core import Observation, action_schema, validate_action
from astra_manipulation.policy import prompt_payload
from astra_manipulation.codex_policy import CodexPolicy


SPEC = {"low": [-1.0, -1.0], "high": [1.0, 1.0]}


def observation():
    return Observation({"wrist": np.zeros((16, 16, 3), dtype=np.uint8)},
                       {"joint_positions": [0.2]}, "Lift the object", 0)


@pytest.mark.parametrize("field,value", [
    ("action", [float("nan"), 0]), ("action", [float("inf"), 0]),
    ("action", [True, 0]), ("action", ["0", 0]),
    ("action", [1.001, 0]), ("action", [-1.001, 0]),
    ("action", [0]), ("action", [0, 0, 0]),
    ("repeat", True), ("repeat", 0), ("repeat", 11), ("repeat", 1.0),
    ("done", 1), ("done", "false"),
])
def test_rejects_invalid_actuator_commands(field, value):
    command = {"action": [0, 0], "repeat": 1, "done": False}
    command[field] = value
    with pytest.raises(ValueError):
        validate_action(command, SPEC)


def test_boundaries_and_exact_keys():
    command = {"action": [-1, 1], "repeat": 10, "done": False}
    assert validate_action(command, SPEC) == command
    with pytest.raises(ValueError):
        validate_action({**command, "success": True}, SPEC)
    assert action_schema(2, 3)["properties"]["repeat"]["maximum"] == 3


def test_prompt_contains_only_observation_spec_and_recent_actions():
    history = [{"action": [i, 0], "repeat": 1, "done": False} for i in range(12)]
    payload = prompt_payload(observation(), SPEC, history)
    assert set(payload) == {"observation", "action_specification", "previous_actions"}
    assert payload["previous_actions"] == history[-8:]
    assert set(payload["observation"]) == {
        "instruction", "step_index", "proprioception", "camera_names"}
    assert payload["observation"]["camera_names"] == ["wrist"]


@pytest.mark.parametrize("item_type", ["command_execution", "mcp_tool_call", "web_search",
                                      "file_change", "collab_tool_call", "unknown_future_tool"])
def test_codex_rejects_tool_execution(monkeypatch, item_type):
    def run(command, **kwargs):
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({
            "type": "item.completed", "item": {"type": item_type}}))
    monkeypatch.setattr("astra_manipulation.codex_policy.subprocess.run", run)
    with pytest.raises(RuntimeError, match="isolation violated"):
        CodexPolicy().act(observation(), SPEC, [])


def test_codex_invocation_isolated_and_validated(monkeypatch):
    from pathlib import Path

    monkeypatch.setenv("CODEX_THREAD_ID", "private-parent-thread")
    monkeypatch.setenv("CODEX_SESSION_ID", "private-parent-session")

    def run(command, **kwargs):
        assert "--ignore-user-config" in command and "--ephemeral" in command
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert 'web_search="disabled"' in command
        assert "features.shell_tool=false" in command
        assert "features.mcp_servers=false" not in command
        assert "mcp_servers={}" in command
        assert "CODEX_THREAD_ID" not in kwargs["env"]
        assert "CODEX_SESSION_ID" not in kwargs["env"]
        directory = Path(command[command.index("--cd") + 1])
        assert {p.name for p in directory.iterdir()} == {"camera_0.png", "action.schema.json"}
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({"action": [0, 0], "repeat": 1, "done": False}))
        return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps({
            "type": "turn.completed", "usage": {"input_tokens": 20}}))

    monkeypatch.setattr("astra_manipulation.codex_policy.subprocess.run", run)
    command, metadata = CodexPolicy().act(observation(), SPEC, [])
    assert command["action"] == [0, 0]
    assert metadata["usage"] == {"input_tokens": 20}
    assert metadata["tool_calls"] == 0


@pytest.mark.parametrize("spec", [
    {"low": [-1, -1], "high": [1]},
    {"low": [], "high": []},
    {"low": [1, -1], "high": [-1, 1]},
    {"low": [-1, -1], "high": [float("nan"), 1]},
    {"low": [float("-inf"), -1], "high": [1, 1]},
])
def test_invalid_specification_cannot_skip_action_validation(spec):
    with pytest.raises(ValueError, match="specification"):
        validate_action({"action": [0, 1000], "repeat": 1, "done": False}, spec)

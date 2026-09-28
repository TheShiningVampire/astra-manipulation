import json

import numpy as np
import pytest

from astra_manipulation.core import Observation
from astra_manipulation.runner import run_episode


class Environment:
    action_spec = {"low": [-1], "high": [1], "control_dt": 0.05}

    def __init__(self, successes=(), terminal_at=None):
        self.successes = successes
        self.terminal_at = terminal_at
        self.steps = 0
        self.closed = False

    def observe(self):
        return Observation({"camera": np.zeros((16, 16, 3), dtype=np.uint8)},
                           {"joint_positions": [0.0]}, "Lift the object", self.steps)

    def reset(self, **kwargs):
        return self.observe()

    def step(self, action):
        self.steps += 1
        return self.observe(), self.steps == self.terminal_at, {
            "success": self.steps in self.successes, "privileged_object_height": 0.42}

    def close(self):
        self.closed = True


class Policy:
    def __init__(self, repeat=10, done=False, invalid=False):
        self.repeat, self.done, self.invalid = repeat, done, invalid
        self.calls = 0

    def act(self, obs, spec, history):
        self.calls += 1
        assert "privileged_object_height" not in json.dumps(obs.text())
        assert "privileged_object_height" not in json.dumps(history)
        return {"action": [2 if self.invalid else 0], "repeat": self.repeat,
                "done": self.done}, {"model": "test"}


@pytest.fixture(autouse=True)
def fake_video(monkeypatch):
    class Video:
        def append_data(self, data):
            pass

        def close(self):
            pass
    monkeypatch.setattr("astra_manipulation.runner.imageio.get_writer", lambda *a, **kw: Video())


def test_repeat_respects_step_budget_and_separates_evaluation(tmp_path):
    env, policy = Environment(successes=(1, 2)), Policy()
    output = tmp_path / "episode"
    report = run_episode(env, policy, output, max_steps=3, provider="neutral")
    assert report["control_steps"] == env.steps == 3
    assert report["model_calls"] == policy.calls == 1
    assert report["success_any_step"] is True
    assert report["success_final_step"] is False
    assert report["longest_success_hold_steps"] == 2
    assert report["is_astra_trial"] is False
    assert env.closed
    assert "privileged_object_height" not in (output / "call_000/input.json").read_text()
    assert "privileged_object_height" in (output / "evaluation.json").read_text()


def test_terminal_interrupts_repeat(tmp_path):
    env = Environment(successes=(2,), terminal_at=2)
    report = run_episode(env, Policy(), tmp_path / "episode")
    assert env.steps == 2
    assert report["status"] == "environment_terminal"
    assert report["success_final_step"] is True


def test_model_done_never_counts_as_success_or_executes_action(tmp_path):
    env = Environment()
    report = run_episode(env, Policy(done=True), tmp_path / "episode")
    assert env.steps == 0
    assert report["status"] == "model_stopped"
    assert report["success_any_step"] is False
    assert report["success_final_step"] is False


def test_invalid_response_never_reaches_actuators(tmp_path):
    env = Environment()
    report = run_episode(env, Policy(invalid=True), tmp_path / "episode")
    assert report["status"] == "error"
    assert "actuator limits" in report["error"]
    assert env.steps == 0
    assert env.closed
    assert report["model_calls"] == 1


def test_call_budget_and_hold_reset(tmp_path):
    env, policy = Environment(successes=(1, 3, 4)), Policy(repeat=1)
    report = run_episode(env, policy, tmp_path / "episode", max_calls=5)
    assert env.steps == policy.calls == 5
    assert report["longest_success_hold_steps"] == 2
    assert report["status"] == "budget_exhausted"


@pytest.mark.parametrize("budget", ["max_calls", "max_steps", "max_repeat"])
@pytest.mark.parametrize("value", [0, -1])
def test_invalid_budget_rejected_before_model_call(tmp_path, budget, value):
    policy = Policy()
    with pytest.raises(ValueError, match="positive"):
        run_episode(Environment(), policy, tmp_path / "episode", **{budget: value})
    assert policy.calls == 0
    assert not (tmp_path / "episode").exists()


def test_failed_model_attempt_is_counted(tmp_path):
    class FailedPolicy:
        def act(self, *args):
            raise TimeoutError("model unavailable")
    env = Environment()
    report = run_episode(env, FailedPolicy(), tmp_path / "episode")
    assert report["model_calls"] == 1
    assert report["status"] == "error"
    assert env.closed


def test_timeout_retry_does_not_advance_simulation_twice(tmp_path):
    class RetryPolicy(Policy):
        def act(self, obs, spec, history):
            if self.calls == 0:
                self.calls += 1
                assert obs.step_index == 0
                raise TimeoutError("transient timeout")
            assert obs.step_index == 0
            return super().act(obs, spec, history)

    env = Environment()
    output = tmp_path / "retry"
    report = run_episode(env, RetryPolicy(repeat=1), output, max_calls=1, max_steps=1, request_retries=1)
    assert report["model_calls"] == 2
    assert report["validated_decisions"] == 1
    assert env.steps == 1
    assert report["error"] is None
    error = json.loads((output / "call_000/attempt_0_error.json").read_text())
    assert error["action_executed"] is False


@pytest.mark.parametrize("component", ["video", "environment"])
def test_cleanup_errors_preserve_report_and_close_environment(tmp_path, monkeypatch, component):
    class Video:
        def append_data(self, data):
            pass

        def close(self):
            if component == "video":
                raise RuntimeError("encoder failed")

    class ClosingEnvironment(Environment):
        def close(self):
            super().close()
            if component == "environment":
                raise RuntimeError("simulator failed")

    monkeypatch.setattr("astra_manipulation.runner.imageio.get_writer", lambda *a, **kw: Video())
    env = ClosingEnvironment()
    output = tmp_path / "episode"
    report = run_episode(env, Policy(done=True), output)
    assert env.closed
    assert report["status"] == "error"
    assert "close failed" in report["error"]
    assert json.loads((output / "result.json").read_text()) == report


def test_live_observation_matches_final_simulation_step(tmp_path):
    output = tmp_path / "episode"
    run_episode(Environment(), Policy(), output, max_steps=3)
    assert json.loads((output / "live.json").read_text())["step"] == 3
    assert (output / "live.png").exists()
    assert not list(output.glob("*.tmp*"))


def test_viewer_confines_file_requests_and_reports_latest_observation(tmp_path, monkeypatch):
    import io
    from astra_manipulation import viewer

    output = tmp_path / "episode"
    report = run_episode(Environment(), Policy(), output, max_steps=3)
    captured = {}

    class Server:
        def __init__(self, address, handler):
            captured["handler"] = handler

        def serve_forever(self):
            pass

    monkeypatch.setattr(viewer, "ThreadingHTTPServer", Server)
    viewer.serve(tmp_path)

    def request(path):
        handler = object.__new__(captured["handler"])
        handler.path = path
        handler.wfile = io.BytesIO()
        codes = []
        handler.send_response = codes.append
        handler.send_error = codes.append
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        handler.do_GET()
        return codes[0], handler.wfile.getvalue()

    code, body = request("/api/state?run=episode")
    state = json.loads(body)
    assert code == 200
    assert state["step"] == 3
    assert state["result"] == report
    assert state["cameras"] == [{"name": "live", "url": "/file?path=episode/live.png"}]
    assert request("/file?path=episode/live.png")[0] == 200
    assert request("/file?path=episode/config.json")[0] == 404
    assert request("/file?path=../outside.png")[0] == 404
    assert request("/api/state?run=..")[0] == 404

from astra_manipulation.media import executed_call, outcome


def test_action_overlay_is_aligned_with_executed_frames():
    first = {"step": 0, "decision": {"repeat": 3, "done": False}}
    second = {"step": 3, "decision": {"repeat": 2, "done": False}}
    stopped = {"step": 5, "decision": {"repeat": 1, "done": True}}
    calls = [first, second, stopped]
    assert executed_call(calls, 0) is None
    assert executed_call(calls, 1) is first
    assert executed_call(calls, 3) is first
    assert executed_call(calls, 4) is second
    assert executed_call(calls, 5) is second
    assert executed_call(calls, 6) is None


def test_outcome_distinguishes_incomplete_trials():
    assert outcome({"status": "error", "success_any_step": True})[0].startswith("ERROR")
    assert outcome({"status": "budget_exhausted"})[0].startswith("BUDGET EXHAUSTED")
    assert outcome({"status": "environment_terminal"})[0].startswith("NO SUCCESS")
    assert "criterion not met at final frame" in outcome({"success_any_step": True})[0]

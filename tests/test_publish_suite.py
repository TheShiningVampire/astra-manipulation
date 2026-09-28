import json
import zipfile

import pytest

from astra_manipulation import publish_suite


@pytest.mark.parametrize("result,expected", [
    ({"success_any_step": False, "success_final_step": False}, "Not achieved"),
    ({"success_any_step": True, "success_final_step": False}, "Transient success only"),
    ({"success_any_step": True, "success_final_step": True}, "Success"),
    ({"success_final_step": True, "error": "TimeoutError"}, "Interrupted"),
    ({"success_final_step": True, "status": "error", "error": None}, "Interrupted"),
    ({"status": "initialization_error"}, "Interrupted"),
])
def test_publication_outcome_distinguishes_transient_and_interrupted(result, expected):
    assert publish_suite.outcome(result) == expected


def test_publication_requires_final_results_before_media_export(tmp_path, monkeypatch):
    monkeypatch.setattr(publish_suite, "TASKS", ["gripper_lift"])
    monkeypatch.setattr(publish_suite, "export_media", lambda *args: pytest.fail("unfinished run exported"))
    with pytest.raises(RuntimeError, match="no final result"):
        publish_suite.publish(tmp_path / "runs", tmp_path / "report")


def test_publication_preserves_trace_attempt_errors_and_video_bundle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(publish_suite, "TASKS", ["gripper_lift"])
    run = tmp_path / "runs" / "gripper_lift"
    call = run / "call_000"
    call.mkdir(parents=True)

    def write(path, content):
        path.write_text(json.dumps(content))

    result = {"status": "budget_exhausted", "error": None, "success_any_step": True,
              "success_final_step": False, "model_calls": 2, "validated_decisions": 1,
              "control_steps": 3, "wall_seconds": 30, "task": "gripper_lift"}
    config = {"instruction": "Lift the red cube"}
    payload = {"observation": {"step_index": 0, "proprioception": {"joint_positions": [0]}}}
    response = {"decision": {"action": [0.5], "repeat": 3, "done": False}}
    timeout = {"type": "timeout", "action_executed": False}
    for name, data in (("result", result), ("config", config), ("action_spec", {}), ("evaluation", [])):
        write(run / (name + ".json"), data)
    write(run.parent / "suite_config.json", {"seed": 17, "max_decisions": 9})
    write(call / "input.json", payload)
    write(call / "response.json", response)
    write(call / "attempt_0_error.json", timeout)
    (run / "live.png").write_bytes(b"image")
    (tmp_path / "README.md").write_text("# Project\n\nOriginal content\n")

    exports = []

    def export(source, destination, title):
        exports.append(str(source))
        (destination / "annotated.mp4").write_bytes(b"movie")
        (destination / "preview.gif").write_bytes(b"gif")
        write(destination / "media.json", {"source_run": str(source),
                                           "result": json.loads((source / "result.json").read_text())})

    monkeypatch.setattr(publish_suite, "export_media", export)
    rows = publish_suite.publish("runs", "reports/pilot", "README.md", "exports/videos")
    assert rows[0]["outcome"] == "Transient success only"
    trace = json.loads((tmp_path / "reports/pilot/gripper_lift/policy_trace.json").read_text())
    assert trace == [{"call": "call_000", "input": payload, "response": response,
                      "request_errors": [timeout]}]
    readme = (tmp_path / "README.md").read_text()
    assert "reports/pilot/gripper_lift/preview.gif" in readme
    assert "| 1 | 2 | 3 |" in readme
    assert "seed: 17" in readme and "decision limit per task: 9" in readme
    assert "seed 0" not in readme and "40 decisions" not in readme
    local = (tmp_path / "reports/pilot/README.md").read_text()
    assert "(gripper_lift/preview.gif)" in local
    with zipfile.ZipFile(tmp_path / "exports/astra-ten-task-videos.zip") as bundle:
        assert bundle.read("gripper_lift.mp4") == b"movie"
        assert json.loads(bundle.read("summary.json"))[0]["outcome"] == "Transient success only"
    # An identical finished result reuses media, including when absolute paths
    # are used, while all repository links stay portable and relative.
    publish_suite.publish(tmp_path / "runs", tmp_path / "reports/pilot", tmp_path / "README.md", "exports/videos")
    assert (tmp_path / "README.md").read_text().count("<!-- TEN_TASK_GALLERY_START -->") == 1
    assert "(reports/pilot/gripper_lift/preview.gif)" in (tmp_path / "README.md").read_text()
    assert len(exports) == 1
    # Changed results must rebuild overlays rather than combine stale footage
    # and outcome labels with the newly copied trace and result.
    result["success_final_step"] = True
    write(run / "result.json", result)
    publish_suite.publish("runs", "reports/pilot", "README.md", "exports/videos")
    assert len(exports) == 2
    # Missing artifacts invalidate an otherwise matching completion manifest.
    (tmp_path / "reports/pilot/gripper_lift/preview.gif").unlink()
    publish_suite.publish("runs", "reports/pilot", "README.md", "exports/videos")
    assert len(exports) == 3
    # A different source is also stale even if its result happens to match.
    cache = tmp_path / "reports/pilot/gripper_lift/media.json"
    cached = json.loads(cache.read_text())
    cached["source_run"] = "other-trial/gripper_lift"
    write(cache, cached)
    publish_suite.publish("runs", "reports/pilot", "README.md", "exports/videos")
    assert len(exports) == 4

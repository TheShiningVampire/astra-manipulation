import json
import zipfile

from astra_manipulation import publish_comparison as report


def test_publish_keeps_baseline_and_exports_exact_traces(tmp_path, monkeypatch):
    run = tmp_path / "runs" / "bullet_reach"
    call = run / "call_000"
    call.mkdir(parents=True)
    for name, value in {
        "config.json": {"instruction": "Reach the visible target."},
        "action_spec.json": {"names": ["x"]},
        "result.json": {"status": "budget_exhausted", "model_calls": 1,
                        "control_steps": 3, "success_any_step": False},
        "evaluation.json": [{"step": 3, "success": False}],
    }.items():
        (run / name).write_text(json.dumps(value))
    raw_input = '{ "observation": {"step_index": 0} }\n'
    raw_response = '{ "decision": { "action": [0.123456789], "repeat": 3, "done": false } }\n'
    (call / "input.json").write_text(raw_input)
    (call / "response.json").write_text(raw_response)
    (run / "rollout.mp4").write_bytes(b"source")
    (run / "live.png").write_bytes(b"image")

    def fake_export(source, target, title):
        for filename in ("annotated.mp4", "preview.gif"):
            (target / filename).write_bytes(b"test media")
        (target / "media.json").write_text(json.dumps({
            "source_run": str(source), "result": report.read_json(source / "result.json"),
            "resolution": [1920, 1536]}))

    monkeypatch.setattr(report, "export_media", fake_export)
    readme = tmp_path / "README.md"
    baseline = "# Astra\n\n<!-- TEN_TASK_GALLERY_START -->\nBaseline unchanged.\n<!-- TEN_TASK_GALLERY_END -->\n"
    readme.write_text(baseline)
    destination, share, archive = tmp_path / "reports/bullet", tmp_path / "exports/videos", tmp_path / "exports/videos.zip"
    for _ in range(2):
        rows = report.publish([run], destination, readme, share, archive)
    assert rows[0]["outcome"] == "Budget exhausted / no success"
    assert readme.read_text().startswith(baseline)
    assert readme.read_text().count(report.BEGIN) == 1
    assert "reports/bullet/bullet_reach/preview.gif" in readme.read_text()
    assert "reports/bullet" not in (destination / "README.md").read_text()
    trace = (destination / "bullet_reach/policy_trace.txt").read_text()
    assert raw_input in trace and raw_response in trace
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {"bullet_reach.mp4", "summary.json", "README.txt"}


def test_result_labels_do_not_hide_errors_or_transient_success():
    assert report.result_label({"status": "error", "success_any_step": True}) == "Interrupted / error"
    assert report.result_label({"success_any_step": True}) == "Transient success only"
    assert report.result_label({"success_final_step": True}) == "Success at end"

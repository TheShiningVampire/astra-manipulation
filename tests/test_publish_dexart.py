import json
import zipfile

import pytest

from astra_manipulation import publish_dexart as publisher


def make_run(tmp_path,task="dexart_faucet",error=False):
    run = tmp_path/"runs"/task
    run.mkdir(parents=True)
    result = {"status":"initialization_error" if error else "budget_exhausted",
              "error":"renderer unavailable" if error else None,"model_calls":0 if error else 2,
              "validated_decisions":0 if error else 1,"control_steps":0 if error else 7,
              "success_any_step":False,"success_final_step":False,"wall_seconds":63}
    (run/"result.json").write_text(json.dumps(result))
    if not error:
        for filename,value in {
            "config.json":{"instruction":"Turn the faucet.","seed":0,"max_calls":13,"max_steps":91,"max_repeat":7,"reasoning":"medium"},
            "action_spec.json":{"asset_id":501,"asset_split":"seen","control_dt":.03,"native_horizon_steps":250},
            "evaluation.json":[{"step":7,"success":False}],"live.json":{"step":7},
        }.items():
            (run/filename).write_text(json.dumps(value))
        (run/"rollout.mp4").write_bytes(b"recording")
        (run/"live.png").write_bytes(b"frame")
        call = run/"call_000"
        call.mkdir()
        (call/"input.json").write_text('{ "observation": {"step_index": 0} }\n')
        (call/"response.json").write_text('{ "decision": {"action": [0.123456789], "done": false, "repeat": 7} }\n')
        (call/"attempt_0_error.json").write_text('{"error": "temporary timeout"}\n')
    return run


def fake_media(run,target,title):
    for name in ("annotated.mp4","preview.gif"):
        (target/name).write_bytes(b"media")
    (target/"media.json").write_text(json.dumps({"source_run":str(run),"result":json.loads((run/"result.json").read_text()),"resolution":[1920,1536]}))


def test_publisher_preserves_other_sections_and_exact_traces(tmp_path,monkeypatch):
    run = make_run(tmp_path)
    monkeypatch.setattr(publisher,"export_media",fake_media)
    readme = tmp_path/"README.md"
    original = "# Main\n\n<!-- BULLET_COMPARISON_START -->\nExisting results.\n<!-- BULLET_COMPARISON_END -->\n"
    readme.write_text(original)
    out,share,archive = tmp_path/"reports",tmp_path/"videos",tmp_path/"videos.zip"
    for _ in range(2):
        rows = publisher.publish([run],out,readme,share,archive)
    assert readme.read_text().startswith(original)
    assert readme.read_text().count(publisher.BEGIN)==1
    text = (out/"README.md").read_text()
    assert "| 13 | 91 | 250 | 7 | 0.03 s | medium |" in text
    assert "501 / seen" in text
    assert "Budget exhausted / no success" in text
    assert rows[0]["config"]["max_calls"]==13
    trace = (out/run.name/"policy_trace.txt").read_text()
    assert (run/"call_000/response.json").read_text() in trace
    assert "temporary timeout" in trace
    assert (out/run.name/"live.json").exists()
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist())=={"dexart_faucet.mp4","summary.json","README.txt"}


def test_initialization_error_is_reported_without_invented_media(tmp_path,monkeypatch):
    run = make_run(tmp_path,error=True)
    monkeypatch.setattr(publisher,"export_media",lambda *args: pytest.fail("No video to export"))
    rows = publisher.publish([run],tmp_path/"reports",None,tmp_path/"videos",tmp_path/"videos.zip")
    assert not rows[0]["media_available"]
    text = (tmp_path/"reports/README.md").read_text()
    assert "Errors / interrupted trials" in text and "renderer unavailable" in text
    assert "preview.gif" not in text
    with zipfile.ZipFile(tmp_path/"videos.zip") as bundle:
        assert not any(name.endswith(".mp4") for name in bundle.namelist())


def test_unfinished_runs_fail_before_writing(tmp_path):
    run = tmp_path/"dexart_laptop"
    run.mkdir()
    output = tmp_path/"reports"
    with pytest.raises(FileNotFoundError):
        publisher.publish([run],output,None,tmp_path/"videos",tmp_path/"archive.zip")
    assert not output.exists()


def test_main_readme_unchanged_without_explicit_argument(tmp_path,monkeypatch):
    run = make_run(tmp_path)
    readme = tmp_path/"README.md"
    readme.write_text("Unchanged\n")
    monkeypatch.setattr(publisher,"export_media",fake_media)
    publisher.publish([run],tmp_path/"reports",None,tmp_path/"videos",tmp_path/"videos.zip")
    assert readme.read_text()=="Unchanged\n"

"""Publish explicitly selected simulator-comparison runs without changing the baseline suite.

python -m astra_manipulation.publish_comparison runs/bullet-pilot/bullet_reach \
    runs/bullet-pilot/bullet_pick_place --readme README.md
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile

from .media import export_media


BEGIN = "<!-- BULLET_COMPARISON_START -->"
END = "<!-- BULLET_COMPARISON_END -->"


def read_json(path):
    return json.loads(path.read_text())


def result_label(result):
    if result.get("error") or result.get("status") in {"error", "initialization_error"}:
        return "Interrupted / error"
    if result.get("success_final_step"):
        return "Success at end"
    if result.get("success_any_step"):
        return "Transient success only"
    if result.get("status") == "budget_exhausted":
        return "Budget exhausted / no success"
    return "No success observed"


def policy_trace(run, destination):
    rows, text = [], []
    for call in sorted(run.glob("call_*")):
        if not call.is_dir():
            continue
        row = {"call": call.name}
        for name, key in (("input.json", "input"), ("response.json", "response")):
            path = call / name
            if path.exists():
                raw = path.read_text()
                row[key] = json.loads(raw)
                text.extend([f"=== {call.name}/{name} ===\n", raw, "\n"])
        errors = []
        for path in sorted(call.glob("attempt_*_error.json")):
            raw = path.read_text()
            errors.append(json.loads(raw))
            text.extend([f"=== {call.name}/{path.name} ===\n", raw, "\n"])
        if errors:
            row["request_errors"] = errors
        rows.append(row)
    (destination / "policy_trace.json").write_text(json.dumps(rows, indent=2) + "\n")
    (destination / "policy_trace.txt").write_text("".join(text).rstrip() + "\n")


def section(rows, prefix=""):
    lines = ["## Separate PyBullet simulator pilot", "",
             "These additional trials explore a different simulator and controller interface. "
             "They are separate from the ten-task MuJoCo pilot: different tasks, initial states, "
             "controllers, and control horizons prevent a controlled simulator comparison. "
             "These few selected trials do not establish a reliable success rate or identify the cause of earlier failures.", "",
             "The table reports recorded evaluator outcomes; exact instructions, request settings, "
             "action specifications, and policy inputs/outputs accompany each recording. "
             "Videos show executed commands and request latency. Simulation playback is slowed "
             "for readability and omits model waiting time; GIFs are compressed overviews.", "",
             "| Task | Recorded outcome | Decisions | Requests | Control steps | Wall time |",
             "|---|---|---:|---:|---:|---:|"]
    for row in rows:
        result = row["result"]
        requests = result.get("model_calls", 0)
        lines.append(f"| {row['title']} | {row['outcome']} | "
                     f"{result.get('validated_decisions', requests)} | {requests} | "
                     f"{result.get('control_steps', 0)} | {result.get('wall_seconds', 0)/60:.1f} min |")
    lines.append("")
    for row in rows:
        base = prefix + row["task"] + "/"
        lines.extend([f"**{row['title']} — {row['outcome']}**", "", row["instruction"], "",
                      f"![{row['title']}]({base}preview.gif)", "",
                      f"[MP4 with Astra commands]({base}annotated.mp4) · "
                      f"[Result]({base}result.json) · [Configuration]({base}config.json) · "
                      f"[Action specification]({base}action_spec.json) · "
                      f"[Exact policy trace]({base}policy_trace.txt)", ""])
    return "\n".join(lines)


def publish(runs, destination="reports/bullet-pilot", readme=None,
            share_directory="exports/bullet-videos", archive="exports/astra-bullet-videos.zip"):
    runs = [Path(run) for run in runs]
    if not runs or len({run.name for run in runs}) != len(runs):
        raise ValueError("Provide at least one run, with distinct directory names")
    # Validate the entire selection before exporting or modifying the README.
    for run in runs:
        for filename in ("result.json", "config.json", "action_spec.json", "rollout.mp4"):
            if not (run / filename).is_file():
                raise FileNotFoundError(run / filename)
    destination, share, archive = Path(destination), Path(share_directory), Path(archive)
    destination.mkdir(parents=True, exist_ok=True)
    rows = []
    for run in runs:
        result, config = read_json(run / "result.json"), read_json(run / "config.json")
        title = "PyBullet · " + run.name.removeprefix("bullet_").replace("_", " ")
        target = destination / run.name
        target.mkdir(exist_ok=True)
        cached = {}
        try:
            cached = read_json(target / "media.json")
        except (OSError, ValueError):
            pass
        matches = (cached.get("source_run") and Path(cached["source_run"]).resolve() == run.resolve()
                   and cached.get("result") == result and cached.get("resolution") == [1920, 1536]
                   and all((target / name).is_file() for name in ("annotated.mp4", "preview.gif")))
        if not matches:
            export_media(run, target, title)
        for filename in ("config.json", "action_spec.json", "result.json", "evaluation.json", "live.png"):
            if (run / filename).exists():
                shutil.copy2(run / filename, target / filename)
        policy_trace(run, target)
        rows.append({"task": run.name, "title": title, "source_run": str(run),
                     "instruction": config.get("instruction", ""), "outcome": result_label(result),
                     "result": result})
    (destination / "summary.json").write_text(json.dumps(rows, indent=2) + "\n")
    (destination / "README.md").write_text(section(rows).rstrip() + "\n")
    share.mkdir(parents=True, exist_ok=True)
    shared_files = []
    for row in rows:
        target = share / (row["task"] + ".mp4")
        shutil.copy2(destination / row["task"] / "annotated.mp4", target)
        shared_files.append(target)
    shutil.copy2(destination / "summary.json", share / "summary.json")
    shared_files.append(share / "summary.json")
    (share / "README.txt").write_text(
        "Astra manipulation: separate PyBullet exploratory pilot\n"
        "MP4 overlays show exact executed actions, request latency, and recorded outcome.\n"
        "Simulation playback is slowed; model-request waiting time is omitted.\n"
        "Different environments/controllers prevent a controlled comparison with the baseline.\n"
        "Results and provenance: summary.json\n"
        "Source: https://github.com/TheShiningVampire/astra-manipulation\n")
    shared_files.append(share / "README.txt")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for path in shared_files:
            bundle.write(path, path.name)
    if readme:
        readme = Path(readme)
        content = readme.read_text()
        prefix = Path(os.path.relpath(destination.resolve(), readme.resolve().parent)).as_posix() + "/"
        block = BEGIN + "\n" + section(rows, prefix) + "\n" + END
        if BEGIN in content and END in content:
            start, stop = content.index(BEGIN), content.index(END) + len(END)
            content = content[:start] + block + content[stop:]
        elif BEGIN in content or END in content:
            raise ValueError("README contains an incomplete PyBullet comparison marker pair")
        else:
            content = content.rstrip() + "\n\n" + block + "\n"
        readme.write_text(content)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--output", default="reports/bullet-pilot")
    parser.add_argument("--readme", type=Path)
    parser.add_argument("--share-directory", default="exports/bullet-videos")
    parser.add_argument("--archive", default="exports/astra-bullet-videos.zip")
    args = parser.parse_args()
    print(json.dumps(publish(args.runs, args.output, args.readme, args.share_directory, args.archive), indent=2))


if __name__ == "__main__":
    main()

"""Build a portable suite report and README gallery from real recorded trials."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

from .media import export_media
from .suite import TASKS

TITLES = {
    "gripper_lift": "Gripper · cube lift", "gripper_stack": "Gripper · cube stacking",
    "gripper_door": "Gripper · door opening", "gripper_nut_assembly_square": "Gripper · square nut assembly",
    "gripper_pick_place_can": "Gripper · can pick-and-place", "hand_ball_lift": "Hand · ball lift",
    "hand_relocate": "Hand · ball relocation", "hand_door": "Hand · door opening",
    "hand_hammer": "Hand · hammering", "hand_pen": "Hand · pen reorientation",
}


def outcome(result):
    if result.get("error"):
        return "Interrupted"
    if result.get("success_final_step"):
        return "Success"
    if result.get("success_any_step"):
        return "Transient success only"
    return "Not achieved"


def publish(root, destination, readme=None, share_directory="exports/ten-task-videos"):
    root, destination = Path(root), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for task in TASKS:
        run = root / task
        if not (run / "result.json").exists():
            raise RuntimeError(f"Task has no final result: {task}")
        result = json.loads((run / "result.json").read_text())
        config = json.loads((run / "config.json").read_text())
        export = destination / task
        export.mkdir(exist_ok=True)
        if not (export / "media.json").exists():
            export_media(run, export, TITLES[task])
        for filename in ("result.json", "config.json", "action_spec.json", "evaluation.json", "live.png"):
            shutil.copy2(run / filename, export / filename)
        # Keep exact allowed input JSON and model response together with each video.
        trace = []
        for call in sorted(run.glob("call_*")):
            row = {"call": call.name, "input": json.loads((call / "input.json").read_text())}
            if (call / "response.json").exists():
                row["response"] = json.loads((call / "response.json").read_text())
            errors = [json.loads(p.read_text()) for p in sorted(call.glob("attempt_*_error.json"))]
            if errors:
                row["request_errors"] = errors
            trace.append(row)
        (export / "policy_trace.json").write_text(json.dumps(trace, indent=2) + "\n")
        results.append({"task": task, "title": TITLES[task], "outcome": outcome(result),
                        "instruction": config["instruction"], **result})
    (destination / "summary.json").write_text(json.dumps(results, indent=2) + "\n")
    shutil.copy2(root / "suite_config.json", destination / "suite_config.json")
    lines = ["## Ten-task Astra pilot", "", "One seeded trial per task, GPT-6 Astra through Codex, medium reasoning, at most 40 decisions each. This is exploratory evidence, not a reliable success-rate estimate. All runs use native seeded simulator resets (seed 0).", "",
             "The hand receives two 768×768 calibrated RGB views; the gripper receives two 512×512 views. Inputs also include robot proprioception and static actuator documentation. Object states and evaluator feedback are excluded. The hand ball-lift task is a custom lift-and-hold subtask; the other tasks use native benchmark success checks. The can destination has a visible green outline.", "",
             "Videos include exact executed Astra action values, repeat count, request latency, simulation time, and final episode outcome. Playback is slowed for readability; model waiting time is omitted. GIFs are compressed overviews of the full trajectory. MP4s retain the larger, readable overlay.", "",
             "| Task | Outcome at end | Decisions | Requests | Control steps | Wall time |", "|---|---|---:|---:|---:|---:|"]
    for row in results:
        lines.append(f"| {row['title']} | {row['outcome']} | {row.get('validated_decisions', row['model_calls'])} | {row['model_calls']} | {row['control_steps']} | {row['wall_seconds']/60:.1f} min |")
    lines.append("")
    # Relative paths differ between the repository README and report-local gallery.
    prefix = destination.as_posix().rstrip("/") + "/" if readme else ""
    for embodiment in ("gripper", "hand"):
        lines += [f"### {embodiment.title()} videos", ""]
        for task in TASKS:
            if not task.startswith(embodiment + "_"):
                continue
            row = next(r for r in results if r["task"] == task)
            lines += [f"**{TITLES[task]} — {row['outcome']}**", "",
                      f"![{TITLES[task]}]({prefix}{task}/preview.gif)", "",
                      f"[MP4 with Astra commands]({prefix}{task}/annotated.mp4) · [Result]({prefix}{task}/result.json) · [Exact policy trace]({prefix}{task}/policy_trace.json)", ""]
    section = "\n".join(lines)
    # Always write a local report with local links.
    local_section = section.replace(prefix, "") if prefix else section
    (destination / "README.md").write_text(local_section + "\n")
    if readme:
        readme = Path(readme)
        content = readme.read_text()
        begin, end = "<!-- TEN_TASK_GALLERY_START -->", "<!-- TEN_TASK_GALLERY_END -->"
        block = begin + "\n" + section + "\n" + end
        if begin in content:
            start, stop = content.index(begin), content.index(end) + len(end)
            content = content[:start] + block + content[stop:]
        else:
            first, rest = content.split("\n", 1)
            content = first + "\n\n" + block + "\n" + rest
        readme.write_text(content)
    share = Path(share_directory)
    share.mkdir(parents=True, exist_ok=True)
    for task in TASKS:
        shutil.copy2(destination / task / "annotated.mp4", share / (task + ".mp4"))
    shutil.copy2(destination / "summary.json", share / "summary.json")
    (share / "README.txt").write_text(
        "Astra manipulation: ten-task exploratory pilot\n"
        "Each MP4 includes the exact executed model commands and final outcome.\n"
        "Playback is slowed for readability and omits model-request waiting time.\n"
        "See summary.json for task results, model calls, errors, and wall time.\n"
        "Public source and GIF gallery: https://github.com/TheShiningVampire/astra-manipulation\n")
    archive = share.parent / "astra-ten-task-videos.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        for path in sorted(share.iterdir()):
            if path.is_file():
                bundle.write(path, path.name)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--output", default="reports/ten-task-pilot")
    parser.add_argument("--readme")
    args = parser.parse_args()
    print(json.dumps(publish(args.root, args.output, args.readme), indent=2))

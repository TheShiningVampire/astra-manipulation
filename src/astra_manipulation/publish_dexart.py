"""Publish the four finalized DexArt pilot runs; README editing requires --readme."""
import argparse
import json
import os
from pathlib import Path
import shutil
import zipfile

from .media import export_media
from .publish_comparison import policy_trace, read_json, result_label

BEGIN = "<!-- DEXART_PILOT_START -->"
END = "<!-- DEXART_PILOT_END -->"
DEFAULT_RUNS = [Path("runs/dexart-pilot") / ("dexart_" + task)
                for task in ("faucet", "laptop", "bucket", "toilet")]
ARTIFACTS = ("config.json", "action_spec.json", "result.json", "evaluation.json", "live.png", "live.json")


def section(rows, prefix=""):
    lines = ["## DexArt / SAPIEN dexterous-hand pilot", "",
        "Four native articulated-object tasks—faucet, laptop, bucket and toilet—are evaluated with "
        "one predetermined seen instance per task and intended seed 0. Actual instance IDs, seeds and "
        "budgets are recorded below. This small pilot does not establish a reliable success rate, "
        "generalization to unseen objects, or a controlled comparison with the other simulators.", "",
        "Astra supplies the native wrist and finger commands using fixed-camera RGB and robot "
        "proprioception. No trained RL policy, expert action sequence or added grasp controller runs "
        "the robot. Outcomes come from DexArt's native task evaluation, including its contact criteria; "
        "errors and interruptions are reported separately from completed trials.", "",
        "Videos overlay exact executed actions and request latency. Simulation playback is slowed "
        "for readability and omits request waiting time; GIFs summarize the full recording. "
        "Exact policy inputs, outputs and request-error traces accompany each result.", "",
        "| Task | Instance / split | Seed | Recorded outcome | Decisions / requests | Steps | Wall time |",
        "|---|---|---:|---|---:|---:|---:|"]
    for row in rows:
        result, config, spec = row["result"], row["config"], row["action_spec"]
        calls = result.get("model_calls", 0)
        lines.append(f"| {row['title']} | {spec.get('asset_id','unreported')} / {spec.get('asset_split','unreported')} | "
            f"{config.get('seed',result.get('seed','unreported'))} | {row['outcome']} | "
            f"{result.get('validated_decisions',calls)} / {calls} | {result.get('control_steps',0)} | "
            f"{result.get('wall_seconds',0)/60:.1f} min |")
    lines.extend(["", "Recorded budgets and interfaces:", "",
        "| Task | Decision budget | Requested step budget | Native horizon | Max repeat | Control interval | Reasoning |",
        "|---|---:|---:|---:|---:|---:|---|"])
    for row in rows:
        c, s = row["config"], row["action_spec"]
        lines.append(f"| {row['title']} | {c.get('max_calls','unreported')} | {c.get('max_steps','unreported')} | "
                     f"{s.get('native_horizon_steps','unreported')} | {c.get('max_repeat','unreported')} | "
                     f"{s.get('control_dt','unreported')} s | {c.get('reasoning','unreported')} |")
    errors = [row for row in rows if row["result"].get("error") or row["result"].get("status") in ("error","initialization_error")]
    if errors:
        lines.extend(["", "Errors / interrupted trials:", ""])
        for row in errors:
            lines.append(f"- {row['title']}: {row['result'].get('error') or row['result'].get('status')}")
    lines.append("")
    for row in rows:
        base = prefix + row["task"] + "/"
        lines.extend([f"**{row['title']} — {row['outcome']}**", "", row["config"].get("instruction","Instruction unavailable."), ""])
        if row["media_available"]:
            lines.extend([f"![{row['title']}]({base}preview.gif)", "", f"[MP4 with Astra commands]({base}annotated.mp4)", ""])
        else:
            lines.extend(["No rollout recording is available for this interrupted/initialization-failed trial.", ""])
        links = [f"[Result]({base}result.json)", f"[Exact policy trace]({base}policy_trace.txt)"]
        for name,label in (("config.json","Configuration"),("action_spec.json","Action specification"),
                           ("evaluation.json","Evaluator record"),("live.png","Final available frame")):
            if name in row["available_artifacts"]:
                links.append(f"[{label}]({base}{name})")
        lines.extend([" · ".join(links), ""])
    return "\n".join(lines)


def publish(runs=None, destination="reports/dexart-pilot", readme=None,
            share_directory="exports/dexart-videos", archive="exports/astra-dexart-videos.zip"):
    runs = [Path(p) for p in (DEFAULT_RUNS if runs is None else runs)]
    if not runs or len({p.name for p in runs}) != len(runs):
        raise ValueError("Select distinct finalized DexArt run directories")
    prepared = []
    for run in runs:
        if run.name not in {p.name for p in DEFAULT_RUNS}:
            raise ValueError(f"Unexpected DexArt task {run.name}")
        result = read_json(run / "result.json")  # absence means not finalized: fail before writes
        error = result.get("error") or result.get("status") in ("error","initialization_error")
        if not error:
            for filename in ("config.json","action_spec.json","evaluation.json","rollout.mp4"):
                if not (run / filename).is_file():
                    raise FileNotFoundError(run / filename)
        config = read_json(run / "config.json") if (run / "config.json").exists() else {}
        spec = read_json(run / "action_spec.json") if (run / "action_spec.json").exists() else {}
        prepared.append((run,result,config,spec))
    if readme:
        readme = Path(readme)
        content = readme.read_text()
        if (BEGIN in content) != (END in content) or content.count(BEGIN)>1 or content.count(END)>1:
            raise ValueError("README has malformed DexArt markers")
        if BEGIN in content and content.index(END) < content.index(BEGIN):
            raise ValueError("README has reversed DexArt markers")
    destination,share,archive = Path(destination),Path(share_directory),Path(archive)
    destination.mkdir(parents=True,exist_ok=True)
    rows = []
    for run,result,config,spec in prepared:
        target = destination / run.name
        target.mkdir(exist_ok=True)
        title = "DexArt · " + run.name.removeprefix("dexart_")
        media_available = bool((run / "rollout.mp4").is_file() and config and spec)
        if media_available:
            cached = {}
            try:
                cached = read_json(target / "media.json")
                same_inputs = read_json(target / "config.json") == config and read_json(target / "action_spec.json") == spec
            except (OSError,ValueError):
                same_inputs = False
            matches = (same_inputs and cached.get("source_run") and
                       Path(cached["source_run"]).resolve()==run.resolve() and cached.get("result")==result and
                       cached.get("resolution")==[1920,1536] and
                       all((target/name).is_file() for name in ("annotated.mp4","preview.gif")))
            if not matches:
                export_media(run,target,title)
        available = []
        for filename in ARTIFACTS:
            if (run/filename).is_file():
                shutil.copy2(run/filename,target/filename)
                available.append(filename)
        policy_trace(run,target)
        rows.append({"task":run.name,"title":title,"source_run":str(run),"outcome":result_label(result),
                     "result":result,"config":config,"action_spec":spec,
                     "media_available":media_available,"available_artifacts":available})
    (destination/"summary.json").write_text(json.dumps(rows,indent=2)+"\n")
    if len({run.parent.resolve() for run in runs}) == 1:
        manifest = runs[0].parent / "suite_config.json"
        if manifest.is_file():
            shutil.copy2(manifest, destination / "suite_config.json")
    (destination/"README.md").write_text(section(rows).rstrip()+"\n")
    share.mkdir(parents=True,exist_ok=True)
    shared = []
    for row in rows:
        if row["media_available"]:
            path = share/(row["task"]+".mp4")
            shutil.copy2(destination/row["task"]/"annotated.mp4",path)
            shared.append(path)
    shutil.copy2(destination/"summary.json",share/"summary.json")
    (share/"README.txt").write_text(
        "Astra: DexArt/SAPIEN exploratory dexterous-hand pilot\n"
        "Four native tasks, one predetermined seen instance per task, intended seed 0.\n"
        "Not a reliable success-rate estimate. No RL controller or expert action trajectory.\n"
        "Native task/contact criteria; actual settings and errors are in summary.json.\n"
        "Videos overlay exact executed actions and request latency. Playback is slowed and omits request waits.\n"
        "Source: https://github.com/TheShiningVampire/astra-manipulation\n")
    shared.extend([share/"summary.json",share/"README.txt"])
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_STORED) as bundle:
        for path in shared:
            bundle.write(path,path.name)
    if readme:
        prefix = Path(os.path.relpath(destination.resolve(),readme.resolve().parent)).as_posix()+"/"
        block = BEGIN+"\n"+section(rows,prefix)+"\n"+END
        if BEGIN in content:
            content = content[:content.index(BEGIN)]+block+content[content.index(END)+len(END):]
        else:
            content = content.rstrip()+"\n\n"+block+"\n"
        readme.write_text(content)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs",nargs="*",type=Path)
    parser.add_argument("--output",default="reports/dexart-pilot")
    parser.add_argument("--readme",type=Path)
    parser.add_argument("--share-directory",default="exports/dexart-videos")
    parser.add_argument("--archive",default="exports/astra-dexart-videos.zip")
    args = parser.parse_args()
    rows = publish(args.runs or None,args.output,args.readme,args.share_directory,args.archive)
    print(json.dumps([{"task":r["task"],"outcome":r["outcome"]} for r in rows],indent=2))


if __name__ == "__main__":
    main()

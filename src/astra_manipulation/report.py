"""Export explicitly selected completed trials with auditable sensor/action traces."""
import argparse
import json
from pathlib import Path
import shutil
import statistics


def export_trials(run_paths, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    summary = []
    for run in map(Path, run_paths):
        result = json.loads((run / "result.json").read_text())
        config = json.loads((run / "config.json").read_text())
        responses = [json.loads(p.read_text()) for p in sorted(run.glob("call_*/response.json"))]
        latencies = [r["metadata"]["latency_seconds"] for r in responses if "latency_seconds" in r["metadata"]]
        usage = [r["metadata"].get("usage") or {} for r in responses]
        row = {"run": run.name, **result, "instruction": config["instruction"],
               "mean_latency_seconds": statistics.mean(latencies) if latencies else None,
               "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
               "output_tokens": sum(u.get("output_tokens", 0) for u in usage)}
        summary.append(row)
        target = destination / run.name
        target.mkdir(exist_ok=False)
        for filename in ("result.json", "config.json", "action_spec.json", "evaluation.json", "rollout.mp4", "live.png"):
            if (run / filename).exists():
                shutil.copy2(run / filename, target / filename)
        for call in sorted(run.glob("call_*")):
            shutil.copytree(call, target / call.name)
    (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = ["# Exploratory Astra trials", "", "These selected completed trials are a pilot, not a statistically reliable success-rate estimate.",
             "Model: requested `gpt-6-astra` via Codex CLI. No privileged task state in model inputs.", "",
             "| Trial | Final success | Calls | Control steps | Wall seconds |", "|---|---:|---:|---:|---:|"]
    for row in summary:
        lines.append(f"| [{row['run']}]({row['run']}/result.json) | {row['success_final_step']} | {row['model_calls']} | {row['control_steps']} | {row['wall_seconds']:.1f} |")
    lines += ["", "Each trial includes a simulation-time MP4, sensor inputs, actuator commands, and separate evaluator data.",
              "Task instructions and initializations differ; this is not a controlled comparison of embodiments or paraphrases."]
    (destination / "README.md").write_text("\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(export_trials(args.runs, args.output), indent=2))

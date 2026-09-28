"""Bounded, resumable orchestration of independent task trials."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys


TASKS = ["gripper_lift", "hand_ball_lift", "gripper_stack", "hand_relocate", "gripper_door",
         "hand_door", "gripper_nut_assembly_square", "hand_hammer", "gripper_pick_place_can", "hand_pen"]


def run_suite(root, tasks=TASKS, workers=2, max_calls=40, seed=0):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"tasks": tasks, "seed": seed, "trials_per_task": 1,
                "max_decisions": max_calls, "max_steps": 800,
                "hand_image_size": 768, "gripper_image_size": 512,
                "request_timeout_seconds": 240, "timeout_retries": 1,
                "reasoning": "medium", "model": "gpt-6-astra"}
    (root / "suite_config.json").write_text(json.dumps(manifest, indent=2) + "\n")

    def run(task):
        output = root / task
        result_path = output / "result.json"
        if result_path.exists():
            return json.loads(result_path.read_text())
        if output.exists():
            raise RuntimeError(f"Incomplete existing run {output}; inspect it instead of overwriting")
        command = [sys.executable, "-m", "astra_manipulation.cli", "--task", task,
            "--provider", "codex", "--seed", str(seed), "--max-calls", str(max_calls),
            "--max-steps", "800", "--max-repeat", "20" if task.startswith("hand_") else "10",
            "--timeout", "240", "--request-retries", "1", "--reasoning", "medium",
            "--output", str(output)]
        environment = dict(os.environ)
        environment.setdefault("MUJOCO_GL", "osmesa")
        with (root / f"{task}.log").open("w") as log:
            completed = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        if result_path.exists():
            result = json.loads(result_path.read_text())
        else:
            result = {"task": task, "status": "initialization_error", "error":
                      f"Process exited {completed.returncode}; see {task}.log"}
        print(json.dumps(result), flush=True)
        return result

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run, task): task for task in tasks}
        for future in as_completed(futures):
            results.append(future.result())
            (root / "suite_results.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--tasks", nargs="+", default=TASKS)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    run_suite(args.output, args.tasks, args.workers, args.max_calls, args.seed)

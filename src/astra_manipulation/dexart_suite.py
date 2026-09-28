"""Four fixed-instance DexArt trials; a pilot, not the full benchmark protocol."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys


TASKS = ["dexart_faucet", "dexart_laptop", "dexart_bucket", "dexart_toilet"]


def run_suite(output, workers=2, max_calls=40):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"tasks": TASKS, "seed": 0, "trials_per_task": 1,
                "initialization": "one predetermined seen instance per task; no pose randomization",
                "max_decisions": max_calls, "max_steps": 250, "max_repeat": 10,
                "image_size": 768, "reasoning": "medium", "requested_model": "gpt-6-astra",
                "provider": "codex", "request_timeout_seconds": 240, "timeout_retries": 1,
                "native_physics_timestep": 0.004, "frame_skip": 10,
                "success": "native is_eval_done; any-step and final-step reported separately",
                "renderer_icd": os.environ.get("VK_ICD_FILENAMES", "automatic"),
                "python": sys.version, "scope": "exploratory pilot, not a generalization benchmark"}
    config = root / "suite_config.json"
    if config.exists() and json.loads(config.read_text()) != manifest:
        raise ValueError("Existing suite configuration differs; choose a new output directory")
    config.write_text(json.dumps(manifest, indent=2) + "\n")

    def trial(task):
        directory = root / task
        result_file = directory / "result.json"
        if result_file.exists():
            return json.loads(result_file.read_text())
        if directory.exists():
            raise RuntimeError(f"Incomplete run exists: {directory}; inspect before retrying")
        command = [sys.executable, "-m", "astra_manipulation.cli", "--task", task,
                   "--provider", "codex", "--seed", "0", "--max-calls", str(max_calls),
                   "--max-steps", "250", "--max-repeat", "10", "--image-size", "768",
                   "--request-retries", "1", "--timeout", "240", "--reasoning", "medium",
                   "--output", str(directory)]
        with (root / (task + ".log")).open("w") as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        result = json.loads(result_file.read_text()) if result_file.exists() else {
            "task": task, "status": "initialization_error", "error": f"Exit {process.returncode}; see {task}.log"}
        print(json.dumps(result), flush=True)
        return result

    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(trial, task) for task in TASKS]):
            results.append(future.result())
            (root / "suite_results.json").write_text(json.dumps(results, indent=2) + "\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="runs/dexart-pilot")
    parser.add_argument("--workers", type=int, choices=[1, 2, 3, 4], default=2)
    parser.add_argument("--max-calls", type=int, default=40)
    args = parser.parse_args()
    if args.max_calls < 1:
        parser.error("max-calls must be positive")
    results = run_suite(args.output, args.workers, args.max_calls)
    if any(row.get("error") for row in results):
        raise SystemExit(1)

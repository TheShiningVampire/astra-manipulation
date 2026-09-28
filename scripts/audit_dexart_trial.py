"""Replay recorded DexArt commands; retain privileged diagnostics only in audit artifacts."""
import argparse
import json
from pathlib import Path

import numpy as np

from astra_manipulation.dexart_tasks import DexArtTaskEnvironment


def audit(run, output):
    config = json.loads((run / "config.json").read_text())
    original = json.loads((run / "evaluation.json").read_text())
    task = config["task"].removeprefix("dexart_")
    env = DexArtTaskEnvironment(task, seed=config["seed"], image_size=64)
    rows, differences, initial = [], [], None
    try:
        obs = env.reset(config["seed"])
        initial = {"progress": getattr(env.env, "progress", None),
                   "success": bool(env.env.is_eval_done),
                   "object_qpos": env.env.instance.get_qpos().tolist()}
        for call in sorted(run.glob("call_*")):
            if not (call / "response.json").exists():
                break
            expected = json.loads((call / "input.json").read_text())["observation"]["proprioception"]
            differences.append({"call": call.name, "max_proprioception_absolute_difference": max(
                float(np.max(np.abs(np.asarray(obs.proprioception[key]) - expected[key]))) for key in expected)})
            decision = json.loads((call / "response.json").read_text())["decision"]
            if decision["done"]:
                break
            for _ in range(decision["repeat"]):
                obs, done, evaluation = env.step(decision["action"])
                native = env.env
                rows.append({"step": env.step_index, "call": call.name, **evaluation,
                             "contact_groups_thumb_index_middle_ring_palm": native.robot_object_contact.tolist(),
                             "palm_to_handle_distance_m": float(np.linalg.norm(native.palm_pose.p-native.handle_pose.p)),
                             "object_qpos": native.instance.get_qpos().tolist()})
                if done:
                    break
            if done:
                break
        max_metric_difference = max((abs(float(row[key])-float(recorded[key]))
            for row, recorded in zip(rows, original) for key in recorded
            if isinstance(recorded[key], (int, float))), default=0.)
        matching = len(rows) == len(original) and max_metric_difference < 1e-9
        report = {"source_run": str(run), "task": task, "seed": config["seed"],
                  "evaluation_only": True, "policy_feedback": False,
                  "method": "Independent reset followed by exact recorded action replay; 64px audit cameras, native physics unchanged.",
                  "initial_state": initial, "steps": len(rows),
                  "evaluation_matches_original_within_1e_9": matching,
                  "max_numeric_evaluation_difference": max_metric_difference,
                  "max_proprioception_difference": max((x["max_proprioception_absolute_difference"] for x in differences), default=0.),
                  "call_observation_checks": differences, "evaluation_with_contacts": rows}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
        print(json.dumps({key:value for key,value in report.items()
                          if key not in ("call_observation_checks", "evaluation_with_contacts")}), flush=True)
    finally:
        env.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    audit(args.run, args.output)

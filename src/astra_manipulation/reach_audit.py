"""Post-run evaluator-only reach audit; never supplies metrics to a policy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .environments import make_environment


def audit_run(run_path, initial_states_path="data/adroit_relocate_initial_states.json", tolerance=1e-8):
    run_path = Path(run_path)
    config = json.loads((run_path / "config.json").read_text())
    # Require finalized runs: do not inspect changing live control trajectories.
    result = json.loads((run_path / "result.json").read_text())
    spec = json.loads((run_path / "action_spec.json").read_text())
    recorded_steps = int(result["control_steps"])
    adapter = make_environment("relocate", config["instruction"], str(initial_states_path), config["max_steps"])
    distances, palms, objects = [], [], []
    steps = checks = 0
    max_error = 0.0
    any_success = final_success = False

    def record_geometry():
        env = adapter.env.unwrapped
        palm = env.data.site_xpos[env.S_grasp_site_id].copy()
        obj = env.data.xpos[env.obj_body_id].copy()
        palms.append(palm)
        objects.append(obj)
        distances.append(float(np.linalg.norm(palm - obj)))

    try:
        adapter.reset(config["seed"], config.get("episode_id"))
        record_geometry()
        for call in sorted(run_path.glob("call_[0-9][0-9][0-9]")):
            observation = json.loads((call / "input.json").read_text())["observation"]
            if int(observation["step_index"]) != steps:
                raise RuntimeError(f"Recorded step index mismatch at {call.name}")
            joints = adapter.env.unwrapped._get_obs()[:30]
            expected = np.asarray(observation["proprioception"]["joint_positions"])
            error = float(np.max(np.abs(joints - expected)))
            max_error = max(max_error, error)
            checks += 1
            if not np.isfinite(error) or error > tolerance:
                raise RuntimeError(f"Replay mismatch at {call.name}: {error} exceeds {tolerance}; refusing reach metrics")
            response_path = call / "response.json"
            if not response_path.exists():
                break
            decision = json.loads(response_path.read_text())["decision"]
            if decision["done"]:
                break
            terminal = False
            for _ in range(min(decision["repeat"], config["max_steps"] - steps, recorded_steps - steps)):
                # Match AdroitEnvironment.step's float32 conversion exactly.
                _, _, terminated, truncated, info = adapter.env.step(np.asarray(decision["action"], dtype=np.float32))
                steps += 1
                final_success = bool(info.get("success", False))
                any_success |= final_success
                record_geometry()
                terminal = bool(terminated or truncated)
                if terminal:
                    break
            if terminal:
                break
        if steps != recorded_steps:
            raise RuntimeError(f"Replayed {steps} steps, expected {recorded_steps}")
        if any_success != bool(result["success_any_step"]) or final_success != bool(result["success_final_step"]):
            raise RuntimeError("Replayed task success differs from recorded evaluation")
        palm_array = np.asarray(palms)
        return {
            "run": run_path.name, "episode_id": config.get("episode_id"), "control_steps": steps,
            "action_spec_version": spec.get("spec_version", "original-confounded-description"),
            "replay_verified": True, "verified_call_observations": checks,
            "joint_replay_max_abs_error": max_error, "joint_replay_tolerance": tolerance,
            "palm_to_ball_distance_initial_m": distances[0],
            "palm_to_ball_distance_min_m": min(distances),
            "palm_to_ball_distance_final_m": distances[-1],
            "closest_step": int(np.argmin(distances)),
            "palm_net_displacement_m": float(np.linalg.norm(palms[-1] - palms[0])),
            "palm_path_length_m": float(np.linalg.norm(np.diff(palm_array, axis=0), axis=1).sum()),
            "ball_net_displacement_m": float(np.linalg.norm(objects[-1] - objects[0])),
            "success_any_step": any_success, "success_final_step": final_success,
            "interpretation": "Evaluator-only geometry from independently verified replay. Palm-site distance is not finger contact or grasp success. Old-spec trials have incorrect action-description confounds.",
        }
    finally:
        adapter.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--initial-states", default="data/adroit_relocate_initial_states.json")
    parser.add_argument("--output", default="docs/hand_reach_audit.json")
    args = parser.parse_args()
    results = [audit_run(path, args.initial_states) for path in args.runs]
    payload = {"evaluation_only": True, "policy_feedback": False, "runs": results}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

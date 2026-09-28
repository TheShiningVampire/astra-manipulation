"""Evaluator-only original demonstration replay. Never an Astra controller."""
from __future__ import annotations

import argparse
import hashlib
import io
from importlib.metadata import version
import json
from pathlib import Path

import numpy as np

from .datasets import ADROIT_RAW_SHA256, _NumericNumpyUnpickler
from .environments import make_environment


def validate_demonstration_replay(raw_path, initial_states_path, episode_ids=(0, 1)):
    content = Path(raw_path).read_bytes()
    if hashlib.sha256(content).hexdigest() != ADROIT_RAW_SHA256:
        raise ValueError("Original demonstration source hash mismatch")
    demos = _NumericNumpyUnpickler(io.BytesIO(content)).load()
    results = []
    for episode_id in episode_ids:
        demo = demos[episode_id]
        actions = np.asarray(demo["actions"])
        adapter = make_environment("relocate", "Evaluator-only original demonstration replay",
                                   str(initial_states_path), len(actions))
        try:
            adapter.reset(0, episode_id)
            initial_error = float(np.max(np.abs(
                adapter.env.unwrapped._get_obs() - demo["observations"][0])))
            success_any = False
            final_success = False
            success_count = longest_hold = hold = 0
            first_success_step = None
            errors = []
            # No rendering/model calls are needed after reset: use the exact same wrapped simulator.
            for index, action in enumerate(actions):
                current_obs = adapter.env.unwrapped._get_obs()
                errors.append(float(np.max(np.abs(current_obs - demo["observations"][index]))))
                _, _, terminated, truncated, info = adapter.env.step(action)
                final_success = bool(info.get("success", False))
                success_any |= final_success
                success_count += int(final_success)
                hold = hold + 1 if final_success else 0
                longest_hold = max(longest_hold, hold)
                if final_success and first_success_step is None:
                    first_success_step = index + 1
                if (terminated or truncated) and index + 1 != len(actions):
                    raise RuntimeError("Replay truncated before the recorded action sequence ended")
            results.append({"episode_id": episode_id, "steps": len(actions),
                            "success_any_step": success_any, "success_final_step": final_success,
                            "success_steps": success_count, "longest_success_hold_steps": longest_hold,
                            "first_success_step": first_success_step,
                            "initial_observation_max_abs_error": initial_error,
                            "trajectory_observation_max_abs_error": max(errors)})
        finally:
            adapter.close()
    return {"baseline": "original_human_demonstration_action_replay", "is_astra_trial": False,
            "source_sha256": ADROIT_RAW_SHA256, "environment": "AdroitHandRelocate-v1",
            "gymnasium_robotics": version("gymnasium-robotics"), "mujoco": version("mujoco"), "episodes": results,
            "interpretation": "Evaluator-only compatibility diagnostic; original actions never enter model policy inputs."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-path", default="data/relocate-v0_demos.pickle")
    parser.add_argument("--initial-states", default="data/adroit_relocate_initial_states.json")
    parser.add_argument("--episodes", nargs="+", type=int, default=[0, 1])
    parser.add_argument("--output", default="docs/replay_validation.json")
    args = parser.parse_args()
    result = validate_demonstration_replay(args.raw_path, args.initial_states, args.episodes)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

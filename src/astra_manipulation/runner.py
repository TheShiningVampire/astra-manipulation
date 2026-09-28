import hashlib
import json
from pathlib import Path
import time
import imageio.v2 as imageio
import numpy as np
from PIL import Image
from .core import validate_action
from .policy import prompt_payload


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def run_episode(env, policy, output, *, seed=0, episode_id=None,
                max_calls=30, max_steps=300, max_repeat=10, provider="api", task=None,
                request_retries=0):
    if min(max_calls, max_steps, max_repeat) < 1:
        raise ValueError("Budgets must be positive")
    if request_retries not in (0, 1, 2):
        raise ValueError("request_retries must be 0, 1 or 2")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    history, records = [], []
    success, consecutive, best_hold = False, 0, 0
    steps, calls, decisions = 0, 0, 0
    status, error = "budget_exhausted", None
    start = time.monotonic()
    video = None
    try:
        obs = env.reset(seed=seed, episode_id=episode_id)
        spec = dict(env.action_spec)
        write_json(output / "action_spec.json", spec)
        write_json(output / "config.json", {"seed": seed, "episode_id": episode_id,
            "provider": provider, "task": task, "instruction": obs.instruction,
            "dataset_path": str(env.dataset_path) if getattr(env, "dataset_path", None) else None,
            "requested_model": getattr(policy, "model", None),
            "reasoning": getattr(policy, "reasoning", None),
            "request_timeout_seconds": getattr(policy, "timeout", None),
            "request_retries": request_retries,
            "max_calls": max_calls, "max_steps": max_steps, "max_repeat": max_repeat})
        video = imageio.get_writer(str(output / "rollout.mp4"), fps=1 / spec["control_dt"])

        def frame(observation):
            images = list(observation.images.values())
            height = max(im.shape[0] for im in images)
            return np.concatenate([np.asarray(Image.fromarray(im).resize(
                (int(im.shape[1] * height / im.shape[0]), height))) for im in images], axis=1)

        def publish(observation, phase):
            pixels = frame(observation)
            temporary = output / "live.tmp.png"
            Image.fromarray(pixels).save(temporary)
            temporary.replace(output / "live.png")
            write_json(output / "live.json", {"step": observation.step_index, "phase": phase})
            video.append_data(pixels)

        publish(obs, "Astra deciding")
        for call in range(max_calls):
            call_dir = output / f"call_{call:03d}"
            call_dir.mkdir()
            spec["control_budget"] = {"decision_index": call, "max_decisions": max_calls,
                "remaining_decisions": max_calls - call, "remaining_control_steps": max_steps - steps,
                "maximum_repeat": max_repeat}
            hashes = {}
            for name, pixels in obs.images.items():
                path = call_dir / (name + ".png")
                Image.fromarray(pixels).save(path)
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            write_json(call_dir / "input.json", prompt_payload(obs, spec, history))
            write_json(output / "live.json", {"step": obs.step_index, "phase": "Astra deciding"})
            for attempt in range(request_retries + 1):
                calls += 1
                try:
                    decision, metadata = policy.act(obs, spec, history)
                    metadata["request_attempts_for_decision"] = attempt + 1
                    break
                except TimeoutError as exc:
                    write_json(call_dir / f"attempt_{attempt}_error.json", {"error": str(exc),
                        "type": "timeout", "action_executed": False})
                    if attempt == request_retries:
                        raise
            decision = validate_action(decision, spec, max_repeat)
            decisions += 1
            write_json(call_dir / "response.json", {"decision": decision, "metadata": metadata,
                                                    "image_sha256": hashes})
            history.append(decision)
            if decision["done"]:
                status = "model_stopped"
                break
            terminal = False
            for _ in range(min(decision["repeat"], max_steps - steps)):
                obs, terminal, evaluation = env.step(decision["action"])
                steps += 1
                current = bool(evaluation.get("success", False))
                success |= current
                consecutive = consecutive + 1 if current else 0
                best_hold = max(best_hold, consecutive)
                records.append({"step": steps, **evaluation})
                # Persist evaluator logs during a trial, separate from policy inputs.
                with (output / "evaluation.jsonl").open("a") as handle:
                    handle.write(json.dumps(records[-1], allow_nan=False) + "\n")
                publish(obs, "Executing Astra command")
                if terminal:
                    status = "environment_terminal"
                    break
            print(json.dumps({"call": calls, "steps": steps, "success": success,
                              "latency": metadata.get("latency_seconds")}), flush=True)
            if terminal or steps >= max_steps:
                break
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {exc}"
    finally:
        try:
            if video is not None:
                video.close()
        except Exception as exc:
            status, error = "error", error or f"Video close failed: {exc}"
        finally:
            try:
                env.close()
            except Exception as exc:
                status, error = "error", error or f"Environment close failed: {exc}"
    report = {"provider": provider, "task": task, "seed": seed, "episode_id": episode_id,
        "status": status, "error": error, "success_any_step": success,
        "success_final_step": bool(records and records[-1].get("success")),
        "longest_success_hold_steps": best_hold, "control_steps": steps,
        "model_calls": calls, "validated_decisions": decisions, "wall_seconds": time.monotonic() - start,
        "is_astra_trial": provider in {"api", "codex"},
        "evaluation_scope": "task_completion_under_authored_instruction"}
    write_json(output / "evaluation.json", records)
    write_json(output / "result.json", report)
    return report

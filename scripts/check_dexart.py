"""Evaluator-only smoke/calibration checks; never invokes or supplies feedback to Astra."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from astra_manipulation.dexart_tasks import DEXART_TASKS, DexArtTaskEnvironment


def snapshot(wrapper):
    native = wrapper.env
    return {"robot_qpos": native.robot.get_qpos().copy(),
            "robot_qvel": native.robot.get_qvel().copy(),
            "palm_position": np.asarray(native.palm_link.get_pose().p).copy(),
            "controller_end_position": np.asarray(native.ee_link.get_pose().p).copy(),
            "object_qpos_evaluator_only": native.instance.get_qpos().copy(),
            "object_pose_evaluator_only": np.r_[native.instance.get_pose().p, native.instance.get_pose().q]}


def differences(first, second):
    return {key: float(np.max(np.abs(first[key] - second[key]))) if first[key].size else 0.
            for key in first}


def finger_hold(wrapper):
    limits = np.asarray(wrapper.action_spec["finger_target_ranges_rad"])
    qpos = wrapper.env.robot.get_qpos()[6:]
    action = np.zeros(22)
    action[6:] = np.clip(2 * (qpos - limits[:, 0]) / (limits[:, 1] - limits[:, 0]) - 1, -1, 1)
    return action


def check(task, output, seed, image_size, source, device):
    wrapper = DexArtTaskEnvironment(task, seed=seed, image_size=image_size,
                                    source_path=source, device=device)
    try:
        obs = wrapper.reset(seed)
        first = snapshot(wrapper)
        initial_success = bool(wrapper.env.is_eval_done)
        images = {}
        for name, pixels in obs.images.items():
            Image.fromarray(pixels).save(output / f"{task}_{name}_initial.png")
            images[name] = {"shape": list(pixels.shape), "dtype": str(pixels.dtype),
                            "minimum": int(pixels.min()), "maximum": int(pixels.max()),
                            "standard_deviation": float(pixels.std())}
        wrapper.reset(seed)
        reset_differences = differences(first, snapshot(wrapper))
        state = obs.proprioception
        robot_sensing_ok = (len(state["joint_positions"]) == len(state["joint_velocities"]) == 22
                            and all(np.isfinite(value).all() for value in state.values()))

        # Run the same held-finger, small XYZ command through adapter and native
        # step from separately reset states. Native oracle is overridden to {}.
        wrapper.reset(seed)
        action = finger_hold(wrapper)
        action[:3] = [0.02, -0.02, 0.02]
        _, adapter_done, adapter_evaluation = wrapper.step(action)
        adapter_state = snapshot(wrapper)
        wrapper.reset(seed)
        native_obs, native_reward, native_done, native_info = wrapper.env.step(action)
        native_state = snapshot(wrapper)
        native_success = bool(wrapper.env.is_eval_done)
        step_differences = differences(adapter_state, native_state)
        reward_difference = abs(float(native_reward) - adapter_evaluation["reward"])

        axes = {}
        for axis, name in enumerate("xyz"):
            wrapper.reset(seed)
            before = snapshot(wrapper)
            pulse = finger_hold(wrapper)
            pulse[axis] = 0.03
            for _ in range(3):
                _, done, _ = wrapper.step(pulse)
                if done:
                    break
            after = snapshot(wrapper)
            wrist_delta = after["controller_end_position"] - before["controller_end_position"]
            palm_delta = after["palm_position"] - before["palm_position"]
            axes[name] = {"command": pulse.tolist(), "requested_ticks": 3,
                          "executed_ticks": wrapper.step_index,
                          "controller_end_displacement_world_m": wrist_delta.tolist(),
                          "palm_displacement_world_m": palm_delta.tolist(),
                          "commanded_axis_displacement_positive": bool(wrist_delta[axis] > 0),
                          "nominal_velocity_m_per_s": 0.03}

        equivalence = (max(step_differences.values()) < 1e-9 and reward_difference < 1e-9
                       and bool(native_done) == adapter_done
                       and native_success == adapter_evaluation["success"] and native_obs == {})
        checks = {
            "initial_success_false": not initial_success,
            "two_nonconstant_rgb_images": len(images) == 2 and all(
                item["dtype"] == "uint8" and item["shape"] == [image_size, image_size, 3]
                and item["standard_deviation"] > 1 for item in images.values()),
            "finite_22_joint_robot_sensing": robot_sensing_ok,
            "deterministic_reset_within_1e_9": max(reset_differences.values()) < 1e-9,
            "adapter_matches_native_step_within_1e_9": equivalence,
            "positive_xyz_pulses_have_positive_commanded_axis_motion": all(
                item["commanded_axis_displacement_positive"] for item in axes.values()),
        }
        return {"task": task, "asset_id": wrapper.asset_id, "seed": seed,
                "evaluation_only": True, "policy_feedback": False,
                "control_dt": wrapper.action_spec["control_dt"],
                "native_horizon_steps": wrapper.action_spec["native_horizon_steps"],
                "checks": checks, "all_checks_pass": all(checks.values()),
                "images": images, "proprioception_keys": list(state),
                "reset_max_absolute_differences": reset_differences,
                "native_comparison": {"action": action.tolist(), "max_absolute_differences": step_differences,
                    "reward_absolute_difference": reward_difference, "adapter_evaluation": adapter_evaluation,
                    "native_reward": float(native_reward), "adapter_done": adapter_done,
                    "native_done": bool(native_done), "native_success": native_success,
                    "native_observation_is_empty": native_obs == {}, "native_info": native_info},
                "axis_pulses": axes,
                "limitations": "Small initial-state pulses verify signs locally, not all-pose IK performance or graspability. Object state is used only to audit reset/native equivalence and is never policy feedback."}
    finally:
        wrapper.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=[*DEXART_TASKS, "all"], default="all")
    parser.add_argument("--output", type=Path, default=Path("runs/dexart-checks"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--image-size", type=int, default=512)
    parser.add_argument("--source")
    parser.add_argument("--device", default="")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tasks = list(DEXART_TASKS) if args.task == "all" else [args.task]
    for task in tasks:
        report = check(task, args.output, args.seed, args.image_size, args.source, args.device)
        (args.output / f"{task}_checks.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"task": task, "checks": report["checks"]}), flush=True)
    reports = [json.loads(path.read_text()) for path in sorted(args.output.glob("*_checks.json"))]
    (args.output / "dexart_runtime_checks.json").write_text(json.dumps({
        "evaluation_only": True, "policy_feedback": False, "tasks": reports}, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

import argparse
import json
import os


def main():
    parser = argparse.ArgumentParser(description="Direct Astra manipulation evaluation")
    parser.add_argument("--backend", choices=["lift", "relocate"], required=True)
    parser.add_argument("--provider", choices=["api", "codex", "neutral"], default="codex")
    parser.add_argument("--instruction")
    parser.add_argument("--dataset-path")
    parser.add_argument("--episode-id", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-calls", type=int, default=30)
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--max-repeat", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=240, help="Per model request timeout in seconds")
    parser.add_argument("--reasoning", choices=["low", "medium", "high", "xhigh", "max"], default="medium")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if min(args.max_calls, args.max_steps, args.max_repeat, args.timeout) < 1:
        parser.error("Budgets must be positive")
    os.environ.setdefault("MUJOCO_GL", "osmesa")
    from .environments import make_environment
    from .policy import AstraPolicy, NeutralPolicy
    from .codex_policy import CodexPolicy
    from .runner import run_episode
    instruction = args.instruction or {
        "lift": "Grasp the red cube with the gripper and lift it above the table.",
        "relocate": "Grasp the blue ball with the dexterous hand and move it to the green target."
    }[args.backend]
    policy = NeutralPolicy() if args.provider == "neutral" else (
        AstraPolicy if args.provider == "api" else CodexPolicy)(
            reasoning=args.reasoning, max_repeat=args.max_repeat, timeout=args.timeout)
    env = make_environment(args.backend, instruction, args.dataset_path, args.max_steps)
    result = run_episode(env, policy, args.output, seed=args.seed, episode_id=args.episode_id,
        max_calls=args.max_calls, max_steps=args.max_steps, max_repeat=args.max_repeat,
        provider=args.provider)
    print(json.dumps(result, indent=2))
    if result["error"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

# Astra Manipulation

Direct GPT-6 Astra control of a robot arm with a parallel gripper, then a dexterous hand. At every decision, Astra receives camera images, measured robot proprioception, a language instruction, static actuator documentation, and its recent actions. It returns a bounded numeric actuator vector and the number of control ticks to execute before observing again.

There is no learned manipulation policy, object-state oracle, grasp planner, or high-level skill executing the task for Astra. Standard low-level operational-space control (Panda) or the native joint actuators (Adroit) convert its commands into physics actions. This is simulation research, not a hardware deployment interface.

## Tasks and observation boundary

| | Arm + gripper | Dexterous hand |
|---|---|---|
| Task | Lift a red cube | Move a blue ball to a green target |
| Robot | Panda, parallel gripper | Adroit Shadow hand, free six-axis arm |
| Dataset | robomimic Lift PH, 200 demos | Original hand_dapg Relocate, 25 demos; Minari copy for inspection |
| Inputs | External + wrist RGB; robot joints, encoder-derived end-effector pose, gripper state | External RGB; 30 robot joint positions/velocities; robot-only palm forward kinematics |
| Outputs | 6 pose deltas + gripper | 30 normalized native actuator controls; audited gains and local axes |
| Initialization | Seed or recorded dataset episode | Seed or recorded hand_dapg episode |

Object poses, relative object/goal vectors, contacts, rewards, success flags, simulator states, and future demonstration actions never enter the policy request. Simulator state is used only for physics, dataset initialization, and evaluation. All policy requests and camera images are recorded for audit.

See [dataset sources and limitations](docs/datasets.md) and [download manifest](docs/dataset_manifest.json). These are different tasks, so differences in success cannot be attributed only to hand dexterity. Instructions are authored prompts, not native dataset language annotations.

## Install

Python 3.11 and a working MuJoCo rendering backend are required. The tested software renderer needs the system OSMesa library (on Debian/Ubuntu: `libosmesa6`). Hardware EGL is also supported by setting `MUJOCO_GL=egl`.

```bash
uv venv --python 3.11
uv pip install --python .venv/bin/python -e '.[sim,test]'
export MUJOCO_GL=osmesa
```

Download demonstrations (not committed or redistributed):

```bash
.venv/bin/python -c 'from astra_manipulation.datasets import download_lift, download_adroit_initial_states; print(download_lift("data")); print(download_adroit_initial_states("data"))'
```

## Run Astra

The default provider uses an installed `codex` CLI and its existing login. Model selection is explicitly `gpt-6-astra`. Every decision runs in a fresh temporary directory with only the permitted images and action schema. Shell, web, apps, plugins, memories, and delegation are disabled. Unexpected tool events invalidate the decision. The CLI may still supply its standard model instructions; this is not identical to a bare API call. The recorded model identifier is the requested identifier because CLI JSON events do not expose a resolved server model.

```bash
.venv/bin/python -m astra_manipulation.cli \
  --backend lift --provider codex \
  --dataset-path data/lift_ph_demo_v15.hdf5 --episode-id 0 \
  --max-calls 30 --max-steps 300 --output runs/lift-0

.venv/bin/python -m astra_manipulation.cli \
  --backend relocate --provider codex \
  --dataset-path data/adroit_relocate_initial_states.json --episode-id 0 \
  --max-calls 30 --max-steps 300 --output runs/hand-0
```

Use `--provider api` with `OPENAI_API_KEY` configured for the OpenAI Responses API. That provider submits PNG images and a strict JSON action schema directly to Astra. Never put keys in this repository. Use `--provider neutral --max-calls 2 --max-steps 2` for a clearly labeled pipeline smoke test. Neutral means actuator-range midpoint, not a stationary controller for the hand.

Override `--instruction` for a paraphrase of the same task. The built-in success predicate remains tied to the selected task: arbitrary new instructions require a matching evaluator. `--reasoning medium`, `--max-repeat 10`, and a 30-call cap are defaults. Simulation pauses during model inference, so this is closed-loop control without a hard real-time guarantee. An episode can end before reaching the step cap because the model-call cap is separate.

## Watch live

```bash
.venv/bin/python -m astra_manipulation.viewer --runs runs
```

Open **http://127.0.0.1:8765** on the machine running the experiment. The viewer follows the newest run, displays camera frames and commands, and offers a video when the run finishes. For a remote machine, forward port 8765 over SSH. Every camera frame is recorded in `rollout.mp4`; the live page samples current frames as commands execute.

## Inspect results

Each run directory contains:

- `config.json`, `action_spec.json`: task, initialization, budgets, and actuator interface.
- `call_*/input.json` and PNGs: exact permitted policy payload and images.
- `call_*/response.json`: validated action, image hashes, latency, and reported token usage.
- `evaluation.json`: evaluator-only per-step rewards and success.
- `result.json`: status, errors, attempted calls, any-step/final-step success, and longest success streak.
- `rollout.mp4`: both camera views where available, at simulation time.

`done` is the model's decision to stop and never establishes task success. Invalid/nonfinite/out-of-range actions fail without being executed; commands are not silently clipped. Errors remain errors, not ordinary task failures. A few trials are exploratory evidence only; report seeds, prompts, budgets, and failures before making success-rate claims. Offline demonstration action agreement is not closed-loop success.

The pinned Lift evaluator checks that the cube center is more than 4 cm above the table surface. Adroit Relocate checks that the ball center is within 10 cm of the target. Neither predicate verifies a particular grasp style. The report separately records the longest continuous success streak; multiply by `control_dt` to obtain its simulated duration.

The [gripper pilot](reports/gripper-pilot/README.md) includes two completed successful Astra trials with full observation/action traces and videos. The [hand simulator compatibility check](docs/replay_validation.json) independently replays original human actions and succeeds on both tested initializations. That replay is not an Astra trial and is never used to guide Astra.

The [corrected hand pilot](reports/hand-corrected-pilot/README.md) completes 30 decisions and 300 simulator steps: the palm reference point approaches within 0.96 cm of the ball center, but relocation is not achieved. This is one exploratory trial, not a general success-rate estimate.

**Pilot caveat:** the first hand trials used an incorrect action description (rotated arm axes and non-unit servo gain were not explained). They are confounded and not a fair measure of Astra's reaching ability. See the [results interpretation](reports/README.md) and [corrected action-space audit](docs/action_space_audit.md).

## Tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q
```

Disabling unrelated host pytest plugins avoids ROS plugin contamination. Tests cover the observation boundary, numeric command validation, tool-event rejection, loop limits, and separation of model stop decisions from evaluator success.

An optional [GitHub Actions template](docs/github-actions-tests.yml) is included. It is not installed as an active workflow because the publishing credential lacks GitHub's `workflow` scope.

## Sources

- [GPT-6 Astra model documentation](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Codex configuration](https://learn.chatgpt.com/docs/config-file/config-reference)
- [robomimic datasets](https://robomimic.github.io/docs/datasets/robomimic_v0.1.html)
- [Adroit Relocate simulator](https://robotics.farama.org/envs/adroit_hand/adroit_relocate/)
- [Minari human relocation dataset](https://minari.farama.org/datasets/D4RL/relocate/human-v2/)

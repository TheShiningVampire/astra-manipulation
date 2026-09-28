# Astra Manipulation

**DexArt/SAPIEN hand evaluation is complete:** 0/4 native benchmark successes. The toilet lid was visibly opened, but the extra native grasp/proximity conditions were not satisfied. [DexArt videos](#dexart--sapien-dexterous-hand-pilot) · [Detailed diagnosis](reports/dexart-pilot/diagnostics.md) · [Protocol and setup](docs/dexart.md).

Latest exploratory results: **MuJoCo ten-task pilot: 0/10 completed goals. PyBullet comparison: 3/3 reaches and 1/1 elevated pick-and-place succeeded.** These are different tasks and control interfaces, not a controlled simulator comparison or a reliable success-rate estimate. [Failure analysis](reports/ten-task-pilot/diagnostics.md) · [PyBullet videos](#separate-pybullet-simulator-pilot) · [Comparison setup](docs/bullet_tasks.md).

<!-- TEN_TASK_GALLERY_START -->
## Ten-task Astra pilot

One recorded trial per task. This is exploratory evidence, not a reliable success-rate estimate. See each task's config.json for its exact initialization, model request, and budgets.

Recorded suite settings: requested model: gpt-6-astra; reasoning: medium; seed: 0; decision limit per task: 40; control-step limit: 800; hand view pixels per side: 768; gripper view pixels per side: 512.

The hand receives two calibrated RGB views; the gripper receives external and wrist RGB views. Inputs also include robot proprioception and static actuator documentation. Object states and evaluator feedback are excluded. The hand ball-lift task is a custom lift-and-hold subtask; the other tasks use native benchmark success checks. The can destination has a visible green outline.

Videos include exact executed Astra action values, repeat count, request latency, simulation time, and final episode outcome. Playback is slowed for readability; model waiting time is omitted. GIFs are compressed overviews of the full trajectory. MP4s retain the larger, readable overlay.

| Task | Outcome at end | Decisions | Requests | Control steps | Wall time |
|---|---|---:|---:|---:|---:|
| Gripper · cube lift | Not achieved | 40 | 40 | 173 | 7.0 min |
| Hand · ball lift | Not achieved | 40 | 40 | 780 | 12.6 min |
| Gripper · cube stacking | Not achieved | 40 | 40 | 138 | 7.4 min |
| Hand · ball relocation | Not achieved | 40 | 40 | 780 | 13.8 min |
| Gripper · door opening | Not achieved | 40 | 40 | 243 | 9.5 min |
| Hand · door opening | Not achieved | 40 | 40 | 780 | 12.6 min |
| Gripper · square nut assembly | Not achieved | 40 | 40 | 180 | 8.0 min |
| Hand · hammering | Not achieved | 40 | 40 | 780 | 10.7 min |
| Gripper · can pick-and-place | Not achieved | 40 | 40 | 236 | 7.4 min |
| Hand · pen reorientation | Not achieved | 14 | 14 | 260 | 4.3 min |

### Gripper videos

**Gripper · cube lift — Not achieved**

![Gripper · cube lift](reports/ten-task-pilot/gripper_lift/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/gripper_lift/annotated.mp4) · [Result](reports/ten-task-pilot/gripper_lift/result.json) · [Exact policy trace](reports/ten-task-pilot/gripper_lift/policy_trace.json)

**Gripper · cube stacking — Not achieved**

![Gripper · cube stacking](reports/ten-task-pilot/gripper_stack/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/gripper_stack/annotated.mp4) · [Result](reports/ten-task-pilot/gripper_stack/result.json) · [Exact policy trace](reports/ten-task-pilot/gripper_stack/policy_trace.json)

**Gripper · door opening — Not achieved**

![Gripper · door opening](reports/ten-task-pilot/gripper_door/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/gripper_door/annotated.mp4) · [Result](reports/ten-task-pilot/gripper_door/result.json) · [Exact policy trace](reports/ten-task-pilot/gripper_door/policy_trace.json)

**Gripper · square nut assembly — Not achieved**

![Gripper · square nut assembly](reports/ten-task-pilot/gripper_nut_assembly_square/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/gripper_nut_assembly_square/annotated.mp4) · [Result](reports/ten-task-pilot/gripper_nut_assembly_square/result.json) · [Exact policy trace](reports/ten-task-pilot/gripper_nut_assembly_square/policy_trace.json)

**Gripper · can pick-and-place — Not achieved**

![Gripper · can pick-and-place](reports/ten-task-pilot/gripper_pick_place_can/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/gripper_pick_place_can/annotated.mp4) · [Result](reports/ten-task-pilot/gripper_pick_place_can/result.json) · [Exact policy trace](reports/ten-task-pilot/gripper_pick_place_can/policy_trace.json)

### Hand videos

**Hand · ball lift — Not achieved**

![Hand · ball lift](reports/ten-task-pilot/hand_ball_lift/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/hand_ball_lift/annotated.mp4) · [Result](reports/ten-task-pilot/hand_ball_lift/result.json) · [Exact policy trace](reports/ten-task-pilot/hand_ball_lift/policy_trace.json)

**Hand · ball relocation — Not achieved**

![Hand · ball relocation](reports/ten-task-pilot/hand_relocate/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/hand_relocate/annotated.mp4) · [Result](reports/ten-task-pilot/hand_relocate/result.json) · [Exact policy trace](reports/ten-task-pilot/hand_relocate/policy_trace.json)

**Hand · door opening — Not achieved**

![Hand · door opening](reports/ten-task-pilot/hand_door/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/hand_door/annotated.mp4) · [Result](reports/ten-task-pilot/hand_door/result.json) · [Exact policy trace](reports/ten-task-pilot/hand_door/policy_trace.json)

**Hand · hammering — Not achieved**

![Hand · hammering](reports/ten-task-pilot/hand_hammer/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/hand_hammer/annotated.mp4) · [Result](reports/ten-task-pilot/hand_hammer/result.json) · [Exact policy trace](reports/ten-task-pilot/hand_hammer/policy_trace.json)

**Hand · pen reorientation — Not achieved**

![Hand · pen reorientation](reports/ten-task-pilot/hand_pen/preview.gif)

[MP4 with Astra commands](reports/ten-task-pilot/hand_pen/annotated.mp4) · [Result](reports/ten-task-pilot/hand_pen/result.json) · [Exact policy trace](reports/ten-task-pilot/hand_pen/policy_trace.json)

<!-- TEN_TASK_GALLERY_END -->

Direct GPT-6 Astra control of a robot arm with a parallel gripper, then a dexterous hand. At every decision, Astra receives camera images, measured robot proprioception, a language instruction, static actuator documentation, and its recent actions. It returns a bounded numeric actuator vector and the number of control ticks to execute before observing again.

There is no learned manipulation policy, object-state oracle, grasp planner, or high-level skill executing the task for Astra. Standard low-level operational-space control (Panda) or the native joint actuators (Adroit) convert its commands into physics actions. This is simulation research, not a hardware deployment interface.

## Tasks and observation boundary

### Why the ten-task pilot failed

All ten trials completed without request errors, but none reached its success criterion. The [trace-based diagnosis](reports/ten-task-pilot/diagnostics.md) separates observed grasp-alignment and recovery failures from hypotheses about temporal context and control budgets. Zero task completions does not mean zero progress: the hand opened its door approximately 62° against a 77° threshold. These are one-off trials, not a general capability estimate.

An additional [PyBullet comparison](docs/bullet_tasks.md) tests simpler Cartesian reaching and grasping with the same image/proprioception-only boundary. It changes both simulator and control interface, so it is not a controlled physics-engine comparison.

The ten-task suite adds five tasks per embodiment: gripper lift, stacking, door opening, square-nut assembly, and can placement; hand ball lifting, relocation, door opening, hammering, and pen reorientation. See the exact [gripper criteria](docs/gripper_tasks.md) and [hand criteria](docs/hand_tasks.md). The table below describes the original dataset-backed pilots; the ten-task suite uses fresh seeded simulator resets.

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

## Reproduce the ten-task suite

```bash
.venv/bin/python -m astra_manipulation.suite \
  --output runs/ten-task-pilot --workers 3 --max-calls 40

.venv/bin/python -m astra_manipulation.publish_suite \
  runs/ten-task-pilot --output reports/ten-task-pilot --readme README.md
```

Use a new output directory for a new experiment. The suite gives each task 40 decision opportunities, an 800-control-tick ceiling, and one retry of a timed-out request on the same frozen observation. Gripper commands can repeat for up to 10 ticks, hand commands for up to 20. Calls execute concurrently across three independent simulators; there is no shared policy state.

For an individual task, use `--task hand_pen` or `--task gripper_stack` with the CLI above instead of `--backend`. Suite cameras are 512×512 per gripper view and 768×768 per hand view; the hand has two fixed calibrated views. These are higher-resolution benchmark renders, not new photorealistic assets.

Publication produces annotated 1920×1536 MP4s, compact README GIFs, exact action traces, and a local sharing bundle at `exports/astra-ten-task-videos.zip`. Overlays show Astra's actual numeric output, repeat count, and stop flag—not an invented explanation. Videos omit inference waiting time and label the simulation-time playback rate. Full original sensor inputs remain in the local run directories.

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

<!-- BULLET_COMPARISON_START -->
## Separate PyBullet simulator pilot

These additional trials explore a different simulator and controller interface. They are separate from the ten-task MuJoCo pilot: different tasks, initial states, controllers, and control horizons prevent a controlled simulator comparison. These few selected trials do not establish a reliable success rate or identify the cause of earlier failures.

The table reports recorded evaluator outcomes; exact instructions, request settings, action specifications, and policy inputs/outputs accompany each recording. Videos show executed commands and request latency. Simulation playback is slowed for readability and omits model waiting time; GIFs are compressed overviews.

| Task | Recorded outcome | Decisions | Requests | Control steps | Wall time |
|---|---|---:|---:|---:|---:|
| PyBullet · reach | Success at end | 1 | 1 | 3 | 0.3 min |
| PyBullet · reach seed1 | Success at end | 1 | 1 | 3 | 0.3 min |
| PyBullet · reach seed2 | Success at end | 1 | 1 | 3 | 0.3 min |
| PyBullet · pick place | Success at end | 10 | 10 | 25 | 2.8 min |

**PyBullet · reach — Success at end**

Move the closed gripper's tip into the magenta target sphere.

![PyBullet · reach](reports/bullet-pilot/bullet_reach/preview.gif)

[MP4 with Astra commands](reports/bullet-pilot/bullet_reach/annotated.mp4) · [Result](reports/bullet-pilot/bullet_reach/result.json) · [Configuration](reports/bullet-pilot/bullet_reach/config.json) · [Action specification](reports/bullet-pilot/bullet_reach/action_spec.json) · [Exact policy trace](reports/bullet-pilot/bullet_reach/policy_trace.txt)

**PyBullet · reach seed1 — Success at end**

Move the closed gripper's tip into the magenta target sphere.

![PyBullet · reach seed1](reports/bullet-pilot/bullet_reach_seed1/preview.gif)

[MP4 with Astra commands](reports/bullet-pilot/bullet_reach_seed1/annotated.mp4) · [Result](reports/bullet-pilot/bullet_reach_seed1/result.json) · [Configuration](reports/bullet-pilot/bullet_reach_seed1/config.json) · [Action specification](reports/bullet-pilot/bullet_reach_seed1/action_spec.json) · [Exact policy trace](reports/bullet-pilot/bullet_reach_seed1/policy_trace.txt)

**PyBullet · reach seed2 — Success at end**

Move the closed gripper's tip into the magenta target sphere.

![PyBullet · reach seed2](reports/bullet-pilot/bullet_reach_seed2/preview.gif)

[MP4 with Astra commands](reports/bullet-pilot/bullet_reach_seed2/annotated.mp4) · [Result](reports/bullet-pilot/bullet_reach_seed2/result.json) · [Configuration](reports/bullet-pilot/bullet_reach_seed2/config.json) · [Action specification](reports/bullet-pilot/bullet_reach_seed2/action_spec.json) · [Exact policy trace](reports/bullet-pilot/bullet_reach_seed2/policy_trace.txt)

**PyBullet · pick place — Success at end**

Grasp the solid green cube and carry its center to the magenta target cube.

![PyBullet · pick place](reports/bullet-pilot/bullet_pick_place/preview.gif)

[MP4 with Astra commands](reports/bullet-pilot/bullet_pick_place/annotated.mp4) · [Result](reports/bullet-pilot/bullet_pick_place/result.json) · [Configuration](reports/bullet-pilot/bullet_pick_place/config.json) · [Action specification](reports/bullet-pilot/bullet_pick_place/action_spec.json) · [Exact policy trace](reports/bullet-pilot/bullet_pick_place/policy_trace.txt)

<!-- BULLET_COMPARISON_END -->

<!-- DEXART_PILOT_START -->
## DexArt / SAPIEN dexterous-hand pilot

Four native articulated-object tasks—faucet, laptop, bucket and toilet—are evaluated with one predetermined seen instance per task and intended seed 0. Actual instance IDs, seeds and budgets are recorded below. This small pilot does not establish a reliable success rate, generalization to unseen objects, or a controlled comparison with the other simulators.

Astra supplies the native wrist and finger commands using fixed-camera RGB and robot proprioception. No trained RL policy, expert action sequence or added grasp controller runs the robot. Outcomes come from DexArt's native task evaluation, including its contact criteria; errors and interruptions are reported separately from completed trials.

Videos overlay exact executed actions and request latency. Simulation playback is slowed for readability and omits request waiting time; GIFs summarize the full recording. Exact policy inputs, outputs and request-error traces accompany each result.

| Task | Instance / split | Seed | Recorded outcome | Decisions / requests | Steps | Wall time |
|---|---|---:|---|---:|---:|---:|
| DexArt · faucet | 148 / seen | 0 | No success observed | 40 / 40 | 250 | 12.0 min |
| DexArt · laptop | 11395 / seen | 0 | No success observed | 40 / 40 | 250 | 8.7 min |
| DexArt · bucket | 100431 / seen | 0 | No success observed | 37 / 37 | 250 | 6.8 min |
| DexArt · toilet | 102677 / seen | 0 | No success observed | 15 / 15 | 120 | 3.0 min |

Recorded budgets and interfaces:

| Task | Decision budget | Requested step budget | Native horizon | Max repeat | Control interval | Reasoning |
|---|---:|---:|---:|---:|---:|---|
| DexArt · faucet | 40 | 250 | 250 | 10 | 0.04000000189989805 s | medium |
| DexArt · laptop | 40 | 250 | 250 | 10 | 0.04000000189989805 s | medium |
| DexArt · bucket | 40 | 250 | 250 | 10 | 0.04000000189989805 s | medium |
| DexArt · toilet | 40 | 250 | 250 | 10 | 0.04000000189989805 s | medium |

**DexArt · faucet — No success observed**

Reach the faucet handle, grasp it with the Allegro hand, and turn the faucet on while maintaining the grasp.

![DexArt · faucet](reports/dexart-pilot/dexart_faucet/preview.gif)

[MP4 with Astra commands](reports/dexart-pilot/dexart_faucet/annotated.mp4)

[Result](reports/dexart-pilot/dexart_faucet/result.json) · [Exact policy trace](reports/dexart-pilot/dexart_faucet/policy_trace.txt) · [Configuration](reports/dexart-pilot/dexart_faucet/config.json) · [Action specification](reports/dexart-pilot/dexart_faucet/action_spec.json) · [Evaluator record](reports/dexart-pilot/dexart_faucet/evaluation.json) · [Final available frame](reports/dexart-pilot/dexart_faucet/live.png)

**DexArt · laptop — No success observed**

Use the Allegro hand to open the laptop lid fully.

![DexArt · laptop](reports/dexart-pilot/dexart_laptop/preview.gif)

[MP4 with Astra commands](reports/dexart-pilot/dexart_laptop/annotated.mp4)

[Result](reports/dexart-pilot/dexart_laptop/result.json) · [Exact policy trace](reports/dexart-pilot/dexart_laptop/policy_trace.txt) · [Configuration](reports/dexart-pilot/dexart_laptop/config.json) · [Action specification](reports/dexart-pilot/dexart_laptop/action_spec.json) · [Evaluator record](reports/dexart-pilot/dexart_laptop/evaluation.json) · [Final available frame](reports/dexart-pilot/dexart_laptop/live.png)

**DexArt · bucket — No success observed**

Grasp the bucket handle and lift the bucket by its handle, keeping the bucket upright.

![DexArt · bucket](reports/dexart-pilot/dexart_bucket/preview.gif)

[MP4 with Astra commands](reports/dexart-pilot/dexart_bucket/annotated.mp4)

[Result](reports/dexart-pilot/dexart_bucket/result.json) · [Exact policy trace](reports/dexart-pilot/dexart_bucket/policy_trace.txt) · [Configuration](reports/dexart-pilot/dexart_bucket/config.json) · [Action specification](reports/dexart-pilot/dexart_bucket/action_spec.json) · [Evaluator record](reports/dexart-pilot/dexart_bucket/evaluation.json) · [Final available frame](reports/dexart-pilot/dexart_bucket/live.png)

**DexArt · toilet — No success observed**

Use the Allegro hand to lift and open the toilet lid fully.

![DexArt · toilet](reports/dexart-pilot/dexart_toilet/preview.gif)

[MP4 with Astra commands](reports/dexart-pilot/dexart_toilet/annotated.mp4)

[Result](reports/dexart-pilot/dexart_toilet/result.json) · [Exact policy trace](reports/dexart-pilot/dexart_toilet/policy_trace.txt) · [Configuration](reports/dexart-pilot/dexart_toilet/config.json) · [Action specification](reports/dexart-pilot/dexart_toilet/action_spec.json) · [Evaluator record](reports/dexart-pilot/dexart_toilet/evaluation.json) · [Final available frame](reports/dexart-pilot/dexart_toilet/live.png)

<!-- DEXART_PILOT_END -->

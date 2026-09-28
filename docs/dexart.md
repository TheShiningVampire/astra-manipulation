# DexArt: direct Astra policy evaluation

This adds the official DexArt tasks in SAPIEN 2.2.1/PhysX, using an xArm6 with
an Allegro hand. Astra receives two fixed calibrated 768×768 RGB views, robot
encoders, and robot-only forward kinematics. It returns all 22 native controls:
six wrist spatial velocities and sixteen absolute finger-joint targets.
No trained RL policy, demonstration action, grasp planner, or task-state oracle
is used to choose actions. Native inverse kinematics and PD drives are retained.

## Reproducible pilot protocol

The completed pilot recorded **0/4 native successes, with no request or
simulator errors**. Toilet's opening progress reached 1.0, but the native
multi-finger grasp and palm-proximity requirements were not simultaneously met.
This is a benchmark failure despite visible completion of the narrower opening
instruction. See the [videos and exact results](../reports/dexart-pilot/README.md)
and [trace-based diagnosis](../reports/dexart-pilot/diagnostics.md).

Four tasks: turn a faucet, open a laptop, lift a bucket, and open a toilet lid.
One predetermined **seen-split** asset per task, seed 0, no pose randomization.
These are four fixed scenarios, not a test of held-out-object generalization or
a reliable success-rate estimate. The benchmark's asset dataset provides the
objects and annotations; this is not a demonstration-dataset evaluation.

Each trial requests GPT-6 Astra through the existing restricted Codex provider,
medium reasoning, up to 40 decisions, 10 repeated ticks per decision, 250 total
ticks (the native horizon), and one retry on a 240-second request timeout.
Physics advances 0.04 seconds per tick and pauses during inference. Native
`is_eval_done` determines success; a model's `done` flag only stops execution.
Any-step success, final-step success, and errors are reported separately.

This changes the task, hand, physics engine, cameras, and action interface from
Adroit. Results cannot isolate the effect of the physics engine alone.

## Isolated runtime

The original DexArt release requests Python 3.8, SAPIEN 2.2.1, and Open3D 0.14.1.
This integration uses a separate Python 3.10 environment and Open3D 0.18.0 for
available wheels. The baseline `.venv` is unchanged; direct source imports are
used because the main project's installation metadata requires Python >=3.11.
The runtime and controller checks must pass before any result is interpreted.

```bash
git clone https://github.com/Kami-code/dexart-release.git data/dexart/source
git -C data/dexart/source checkout d6ab75e1a0b81384d1ac918cbfd4d97b1f230149
# Obtain the official assets and verify their hash: see dexart_assets.md.
uv venv --python 3.10 .venv-dexart
uv pip install --python .venv-dexart/bin/python -r requirements-dexart.txt
export PYTHONPATH=src
# On the tested machine only: working Intel Vulkan, unavailable NVIDIA driver.
export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/intel_icd.json
.venv-dexart/bin/python -m astra_manipulation.dexart_suite --output runs/dexart-pilot
```

The recorded pilot runs four independent processes concurrently (`--workers 4`).
Each process has its own simulator and policy observation directory.

## Validation

All four tasks passed [recorded runtime checks](dexart_runtime_checks.json):
initial success false, two nonconstant RGB images, finite 22-joint sensing,
deterministic resets, native-step equivalence within 1e-9, and positive measured
motion for isolated positive X/Y/Z commands. These small diagnostic pulses are
not expert task demonstrations and are never included in Astra's history.

```bash
.venv-dexart/bin/python scripts/check_dexart.py --task all \
  --output runs/dexart-checks-new --image-size 768
.venv/bin/python -m astra_manipulation.publish_dexart --readme README.md
```

Publication writes `reports/dexart-pilot/`, copies MP4s into
`exports/dexart-videos/`, and creates `exports/astra-dexart-videos.zip`.

The Vulkan ICD path is machine-specific, not a universal SAPIEN setting. Use a
working compatible graphics device on other hosts. Do not replace RGB with
privileged state merely because rendering fails.

See [asset provenance and licensing](dexart_assets.md) and the
[native controller/success audit](dexart_control_audit.md). Third-party assets
remain under ignored `data/`, not redistributed in this repository. The report
publisher exports annotated MP4s, GIFs, policy traces, and a local sharing ZIP.

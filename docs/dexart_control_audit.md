# DexArt control and observation audit

Audited official [Kami-code/dexart-release](https://github.com/Kami-code/dexart-release)
commit `d6ab75e1a0b81384d1ac918cbfd4d97b1f230149`, locally cloned under
`data/dexart/source`. This is a source audit, not a completed runtime calibration
or claim that Astra has succeeded on DexArt. It covers faucet, laptop, toilet,
and bucket using the official factory's default robot.

## Native action semantics

The factory selects `allegro_hand_xarm6_wrist_mounted_face_front`: a six-joint
xArm with a 16-joint Allegro hand. Its 22-dimensional normalized action is
**not** 22 joint-position commands and is not the Adroit interface.

| Coordinates | Actual interpretation |
|---|---|
| 0–2 | Desired end-link linear velocity, normalized −1…1 maps to −1…1 m/s |
| 3–5 | Desired end-link angular velocity, normalized −1…1 maps to −1…1 rad/s |
| 6–21 | Absolute hand joint target: `q_low + (a+1)/2*(q_high-q_low)` |

`arm_sim_step` obtains the arm's spatial Jacobian, solves damped least squares
with damping 0.05, clips resulting arm joint velocities to ±π rad/s, and sets
`q_arm_target = q_arm_current + qvel_arm * control_time_step`. It sets arm
velocity drive targets too. Hand velocity targets are zero; its normalized
actions map directly to absolute joint-limit targets. Zero hand action means
joint-range midpoint, not keep-current-position. A hold approximation for
the fingers is `a=2*(q-q_low)/(q_high-q_low)-1`, subject to valid finite limits.

The Jacobian is computed on a copied arm articulation whose root rotation is
identity. All four task robot root rotations are identity, so its axes align
with world axes in the audited task setups. Translation of the root does not
rotate these velocity axes. Do not reuse that world-frame statement if the
robot base is rotated without checking the controller. The controlled arm
end link is selected by the final arm joint. It is not necessarily coincident
with the palm link used by reward/contact code: expose and name both robot FK
frames if useful, rather than silently calling either one the other.

All four simulator tasks set physics timestep 0.004 s. The factory defaults
to `frame_skip=10`, yielding 0.04 s per environment step. Direct RL class
constructors instead default to 5, yielding 0.02 s. Read and record the actual
`env.control_time_step`. All native horizons are 250 environment steps, hence
10 s with factory defaults. Repeats reissue the same velocity and hand target;
do not execute repeated actions past native termination.

Native arm drives use stiffness/damping/force-limit `[200000,40000,500]`, and
finger drives `[200,60,10]`, in force mode. Upstream explicitly describes the
arm PD as much larger than physical values for stability. These are native
simulation controls, not evidence of physical hardware performance. Validate
bounded finite commands before upstream silently clips them.

Source: [base controller](https://github.com/Kami-code/dexart-release/blob/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/env/rl_env/base.py),
[kinematic model](https://github.com/Kami-code/dexart-release/blob/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/utils/kinematics_helper.py),
[robot loading](https://github.com/Kami-code/dexart-release/blob/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/utils/common_robot_utils.py).

## Robot sensing and RGB boundary

Construct a new observation whitelist from `robot.get_qpos()`,
`robot.get_qvel()`, named robot-link poses/velocities, and camera RGB only.
Get joint names and limits from the robot's active joints; do not assume a
finger ordering from another hand. SAPIEN poses use quaternion **wxyz**,
unlike the earlier MuJoCo-facing xyzw descriptions. Label that explicitly.

The audited `get_robot_state()` methods contain robot qpos, palm linear/angular
velocity, palm world position, and elapsed fraction; bucket additionally has
the palm's local-X direction's world-Z component. Their methods named
`get_oracle_state()` happen to return the same robot-only vector at this commit.
Nevertheless, `get_visual_observation()` automatically includes an
`oracle_state` field and history may include `previous-oracle_state`. Do not
forward the generic upstream dictionary: future or alternate implementations
can change that content. Build the allowlist independently.

Exclude `instance` qpos/pose, `handle_pose`, `handle_in_palm`, progress,
openness, contact arrays, stage/state, reward, `is_eval_done`, segmentation,
`seg_gt`, and imagination clouds from policy inputs. Some imagination modes
explicitly transform object mesh samples using simulator object poses.

The factory defaults to point clouds and `no_rgb=True`. `is_eval=True` enables
RGB-capable offscreen rendering and adds visualization cameras, but does not
automatically replace the point-cloud observation configuration with RGB.
Choose RGB-only observation configuration explicitly, or read only the
selected cameras directly after `scene.update_render()` and `cam.take_picture()`.
Use the SAPIEN camera Color RGBA float texture, first three channels, clipped
to [0,1] and multiplied by 255 before uint8 conversion. Do not cast normalized
RGB directly to uint8, which would produce almost-black images.

Avoid the factory's point-cloud path merely to obtain RGB: it performs
unnecessary CUDA/DLPack work and may introduce segmentation/imagination fields.
The normal static task camera has 64×64 resolution and a 69.4° field of view;
visualization cameras are 1000×1000. Any higher-resolution policy cameras are
an explicit observation-interface change, not the paper's original setting.
Camera placement must stay fixed or robot-attached, not track hidden handles.

## Native success is task-specific

Read `bool(env.is_eval_done)` immediately after native `step`. Base
`get_info()` returns an empty dictionary; there is no native `info['success']`.
The official evaluation script records success if this property becomes true
at any step. Preserve both any-step and final-step metrics in our report.

| Task | `is_eval_done` at this commit | Native termination |
|---|---|---|
| Faucet | Absolute manipulated hinge angle >1.5 rad, palm within 0.2 m of handle, at least two finger groups and palm contact handle | Success or 250 steps |
| Laptop | Progress >0.95, palm within 0.2 m of handle, at least two finger groups and palm contact handle | Success or 250 steps |
| Toilet | Progress >0.95, palm within 0.1 m of handle, at least two finger groups contact handle; palm contact not required | Success or 250 steps |
| Bucket | Handle progress >0.7 and bucket-base height increase >0.25 m | 250 steps only, even if successful |

Laptop/toilet progress is
`1 - abs(q-middle)/(abs(left-middle)-init_open_rad)`; the initial opening offset
is 0.2 rad for laptop and 0.25 rad for toilet. Bucket handle progress is
`1-abs(q-middle)/abs(left-middle)` and height change is clamped below at zero.
The annotations supply `left` and `middle`; use the native predicate rather
than inventing a universal hinge-angle threshold. Confirm the rendered
initial/target interpretation before authoring "open" versus "close" wording.

Bucket's stronger `early_done` is **not** its evaluation predicate:
progress >0.9, stage 3 (including at least three finger groups contacting the
handle), and height increase >0.3 m. Its `is_done()` deliberately ignores that
early flag. Using it instead of `is_eval_done` would misreport native results.
Do not add contact requirements to bucket's evaluation without labeling a
separate custom metric.

Sources: [task RL implementations](https://github.com/Kami-code/dexart-release/tree/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/env/rl_env),
[official evaluation loop](https://github.com/Kami-code/dexart-release/blob/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/examples/evaluate_policy.py).

## Reproducible instances and reset seeds

The constructor's integer `index` is a **position in `TASK_CONFIG[task]`**, not
a PartNet asset ID. After creation `env.index` is the actual asset ID. A list
argument instead contains asset IDs and enables replacement at resets. A
singleton list works but needlessly reloads the object. For a fixed test,
use `index=TASK_CONFIG[task].index(asset_id)` and verify `env.index` afterward.

| Task | Example seen asset / constructor index | Example unseen asset / constructor index |
|---|---|---|
| Faucet | 148 / 0 | 1556 / 11 |
| Laptop | 11395 / 6 | 9748 / 0 |
| Bucket | 100431 / 0 | 100468 / 11 |
| Toilet | 102677 / 11 | 101320 / 0 |

These are examples, not a balanced evaluation split. Exact complete splits
are in upstream `TRAIN_CONFIG`; full asset ordering is in `TASK_CONFIG`.
Log task, actual asset ID, index, seen/unseen split, seed, randomization ranges,
robot name, frame skip, source commit, and asset hashes.

Calling task `reset(seed=...)` alone does **not** seed these implementations:
the parameter is accepted but unused. Object pose noise uses global NumPy RNG;
Laptop list selection uses Python `random.randint`. Seed NumPy and Python
`random` before construction, because constructors reset automatically; call
`env.seed(seed)` for the environment's own RNG and seed the global RNGs again
before the intended reset. Camera perturbation uses `self.np_random`.
Use one process per independent trial to avoid shared global RNG interference.
With fixed instance and zero randomization, changing seed need not change the
initial scene; do not advertise those as varied placements.

Read-only native reset annotations are simulator initialization, not permitted
policy observations. Assets live under `assets/` at the upstream repository
root. Several task loaders parse annotation metadata for all
task assets during setup, even when using one fixed asset, so downloading only
the chosen mesh may be insufficient.

Sources: [factory](https://github.com/Kami-code/dexart-release/blob/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/env/create_env.py),
[task settings/splits](https://github.com/Kami-code/dexart-release/blob/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/env/task_setting.py),
[simulator task loaders](https://github.com/Kami-code/dexart-release/tree/d6ab75e1a0b81384d1ac918cbfd4d97b1f230149/dexart/env/sim_env).

Before an Astra trial, runtime checks should verify 22 dimensions/finite hand
limits, robot joint ordering and end-link frame, real control_dt, a repeatable
reset, readable RGB, and native success initially false. A small isolated
robot-only velocity pulse can verify signs against measured FK. Keep all
object/contact checks evaluator-only and label any renderer compatibility
patches separately from task/controller changes.

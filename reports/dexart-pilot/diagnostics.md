# DexArt pilot audit and diagnostics

## Observation and control audit

Before completion, the first recorded policy request (`call_000/input.json`)
and response were inspected for all four tasks: faucet, laptop, bucket, toilet.
Each request contains only the instruction, step index, robot proprioception,
camera names, static action documentation, remaining control budget, and
previous actions. The proprioception allowlist is exactly:

- 22 robot joint positions and velocities;
- palm world position and rotation;
- controller end-link world position and rotation.

No object qpos/pose, handle pose, contact labels, native progress, openness,
height increase, reward, success, oracle-state dictionary, segmentation, or
object imagination point cloud was present. Static metadata does include task,
asset ID, seen split, robot joint limits/URDF axes, fixed camera calibration,
and source/package provenance. Asset identity is disclosed; hidden dynamic
object state is not. Both 768×768 camera PNG hashes matched the recorded
response for every first decision. First responses were valid 22-dimensional
commands, with native wrist velocity controls followed by absolute normalized
finger joint targets.

The separate [runtime audit](../../docs/dexart_runtime_checks.json) passed all
checks for all four fixed assets: initial native success false, nonconstant RGB,
finite 22-joint sensing, deterministic reset, and positive XYZ pulse signs
measured through robot FK. Adapter/native one-step comparisons matched robot
and object state, reward, done, and success within 1e-9. These calibration
checks establish local controller mapping and observation isolation; they do
not establish graspability or all-pose IK behavior.

All tasks use the native xArm6 + Allegro controller and native `is_eval_done`
predicate. Native simulation steps are approximately 0.04 s, with a 250-step
horizon, so a full episode has approximately ten simulated seconds. Inference
pauses physics. More details, including bucket's distinct success and
termination predicates, are in the [source audit](../../docs/dexart_control_audit.md).

## Trial outcome status

All four trials are complete with no infrastructure errors. Native benchmark
success is **0/4**, but this does not mean no language-directed manipulation:
the toilet lid visibly opens and reaches the native opening-angle target,
while failing additional contact/proximity conditions that were not explicit
in the language instruction. Faucet partially turns; bucket is not lifted;
laptop opens only slightly. These are four exploratory single-instance trials,
not a general success-rate estimate.

Independent exact-action replays also matched every recorded evaluation row
and per-call robot observation with zero numeric difference for
[faucet](faucet_replay_audit.json), [laptop](laptop_replay_audit.json),
[bucket](bucket_replay_audit.json), and [toilet](toilet_replay_audit.json).
These diagnostic replays use privileged state only for offline evaluation;
none of that information was fed back to Astra.

| Task | Decisions | Executed ticks | Native outcome | Observed task progress |
|---|---:|---:|---|---|
| Faucet | 40 | 250 | Failure, horizon | Peak turn 28.56°, below 85.94° threshold |
| Laptop | 40 | 250 | Failure, horizon | Peak opening progress 0.04649 |
| Bucket | 37 | 250 | Failure, horizon | No positive bucket-base height gain |
| Toilet | 15 | 120 | Failure, model stop | Lid opens; opening progress peaks at 1.0, but native grasp/proximity requirements fail |

### Faucet: partial turning without the required grasp

Faucet reaches the 250-tick native horizon after 40 validated decisions.
Absolute hinge angle peaks at 0.498528 rad (28.56°), then finishes at
0.258328 rad (14.80°), below the >1.5 rad (85.94°) native threshold. Its native
two-finger-plus-palm contact predicate remains false throughout. It spends
232 of 250 ticks in stage 2 (near the handle but lacking the required grasp),
18 ticks in stage 1, and never enters stage 3.

Final images show the hand above/near the handle rather than enclosing it.
The last command (`call_039`) includes +0.65 rad/s wrist-Z angular velocity
and curled finger targets, repeat 5, done=false; the native horizon ends the
trial. The model does attempt rotation, and the object measurably turns, but
neither sufficient rotation nor the required simultaneous grasp is achieved.
The composite contact predicate alone does not exclude individual finger
contacts, and no finer contact claim is made here.

Sources: [evaluation](dexart_faucet/evaluation.json),
[result](dexart_faucet/result.json), [trace](dexart_faucet/policy_trace.json),
[final views](dexart_faucet/live.png).

### Bucket: handle moves, bucket is not lifted

Bucket reaches the native 250-tick horizon (approximately ten simulated
seconds), using 37 validated decisions. Handle progress peaks at 0.221081,
then returns to zero. Logged bucket-base height increase is exactly zero at
every step. Native success requires handle progress >0.7 and height increase
>0.25 m; neither threshold is reached. The three-finger contact predicate is
false throughout, and the native stage never advances beyond stage 2.

The final cameras show a curled hand above the bucket handle rather than
holding it. The last issued action (`call_036`) commands +0.25 m/s wrist-Z
with curled finger targets, repeat 3, done=false. The simulator executes to
its horizon; this is not an early model stop or an unexecuted final action.
The logged evidence supports incomplete handle grasp/lift. It does not imply
that no individual finger ever touched the object: the contact predicate
requires three groups, and per-group contacts were not recorded in this trial.

Sources: [evaluation](dexart_bucket/evaluation.json),
[result](dexart_bucket/result.json), [trace](dexart_bucket/policy_trace.json),
[final views](dexart_bucket/live.png).

### Laptop: small lid movement, no native reaching/grasp stage

Laptop reaches 250 ticks and 40 validated decisions. Opening progress peaks
at 0.046492 and finishes at 0.038142, far below the native >0.95 threshold.
The native stage remains 1 throughout, meaning the palm stays more than
0.20 m from the annotated handle point; the two-finger-plus-palm contact
predicate never becomes true. Final views show the lid still nearly closed
and the hand above the lid. This is limited lid movement, not a completed
opening obscured only by the contact criterion.

The last response (`call_039`) has done=false and requests negative X/Z
velocity and negative Y angular velocity for five ticks. Native horizon
termination ends the trial. Unlike the earlier MuJoCo gripper pilot, this
trial does use rotational control; its failure cannot be attributed simply
to never commanding orientation changes.

Sources: [evaluation](dexart_laptop/evaluation.json),
[result](dexart_laptop/result.json), [trace](dexart_laptop/policy_trace.json),
[final views](dexart_laptop/live.png).

### Toilet: lid visibly opens, native contact condition not achieved

The toilet trial stops after 15 decisions and 120 executed ticks (approximately
4.8 s), with no infrastructure error and native success false throughout.
Native opening progress first exceeds 0.95 at step 90 and finishes at
0.987655; its peak is 1.0. The final two camera views show the lid upright and
the hand above it. Thus the robot makes substantial, visually evident progress
toward the authored instruction to open the lid.

DexArt's native predicate additionally requires at least two finger groups
contacting the manipulated lid and the palm within 0.10 m of the annotated
handle point. In the logged high-opening-progress steps, `is_contact=0` and
`state=1`. Native state 1 specifically means palm-to-handle distance exceeds
0.10 m. The two-finger contact predicate was true earlier, at steps 14, 15,
and 17–20, when the opening criterion was not met. The episode therefore never simultaneously
meets opening, proximity, and contact requirements. It should be described as
**visually opened / native benchmark failure**, not as no object motion or as
official success.

The final response at `call_014` sets done=true with zero wrist velocity and
open-finger targets. That response executes no action. The lid is already
open in the preceding observation, so the stop convention does not explain
the missing simultaneous native contact criterion.

Sources: [result](dexart_toilet/result.json),
[evaluation](dexart_toilet/evaluation.json), [final views](dexart_toilet/live.png),
[trace](dexart_toilet/policy_trace.json).

The [independent replay audit](toilet_replay_audit.json) reproduces all 120
evaluation rows and every recorded per-call robot observation with zero
numeric difference. At all 31 high-progress steps (90–120), only the thumb
contact group touches the lid; index, middle, ring, and palm groups are zero.
Thus `is_contact=0` does not mean no physical contact: it means fewer than the
required two finger groups. Palm-to-annotated-handle distance is 0.28194–0.30471 m
over those steps and 0.29142 m at the end, also failing the 0.10 m proximity
requirement. Earlier two-finger contact is thumb plus index, with distance
0.11709–0.15246 m, already outside that proximity threshold. These explain the
official failure despite the visibly opened lid without changing its criterion.

### Language goal versus benchmark predicate

The authored toilet instruction asks to lift and open the lid fully; it does
not explicitly require two finger groups to remain in contact or the palm to
stay within 10 cm of the annotated handle point. The observed lid opening
therefore fulfills a narrower visible outcome consistent with that language,
while the unchanged native benchmark classifies failure. This is an evaluator
alignment limitation, not grounds to silently redefine success. Report native
success alongside observed object outcomes; an unqualified "all tasks failed"
would conceal this distinction. The same extra contact/proximity requirements
exist for laptop, but laptop also falls far short on opening progress itself.

No live policy, source, instruction, or task criterion was changed by this audit.

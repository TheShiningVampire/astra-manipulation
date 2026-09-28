# Failure diagnosis: observations, interface limits, and controlled follow-ups

This examines all ten completed baseline trials: five gripper tasks and five
hand tasks. It also records independently replayed successes in the separate
PyBullet reaching comparison. Neither sample estimates general model capability.

## Completed-task evidence

All ten baseline trials recorded no infrastructure error, `model_stopped`,
and no evaluator success. Nine used 40 validated decisions; pen reorientation
stopped after 14. Failure does not mean no
physical progress: the hand Door trial substantially opened its door.

| Task | Executed ticks | Simulated seconds | Evaluator evidence |
|---|---:|---:|---|
| Gripper Lift | 173 | 8.65 | No successful lift |
| Gripper Stack | 138 | 6.90 | No successful stack |
| Gripper Door | 243 | 12.15 | Maximum hinge angle 0.0000006205 rad; effectively unopened |
| Gripper square nut | 180 | 9.00 | No native insertion success |
| Gripper can placement | 236 | 11.80 | Can never registered in destination compartment |
| Hand ball lift | 780 | 7.80 | Maximum ball-center height 0.03555 m; required >0.10 m for five ticks |
| Hand relocation | 780 | 7.80 | Closest palm-to-ball distance 0.00973 m; object later falls below tabletop |
| Hand Door | 780 | 7.80 | Maximum hinge angle 1.07478 rad (61.6°), final 0.92750 rad (53.1°); native threshold 1.35 rad (77.3°) |
| Hand hammer | 780 | 7.80 | Nail-to-goal distance stays exactly 0.091 m; native threshold 0.01 m |
| Hand pen | 260 | 2.60 | Maximum orientation similarity 0.2424; final goal distance 0.2929 m |

Values come from each task's `result.json`, `evaluation.json`, and
`action_spec.json`. These evaluator measurements were not sent to Astra.

Hand ball lift reaches its closest palm-to-ball distance, 4.43 cm, at step 310,
but ball height never approaches the success threshold. The final images show
the hand beside/over the ball rather than a held lift. Hand relocation reaches
0.97 cm palm-site distance at step 90, but its maximum ball height is only
5.10 cm at step 126. The ball first falls below tabletop height at step 583,
reaches −0.993 m at step 622, and ends below the table. Close palm-site distance
is not a successful finger grasp. Final images show an empty hand near the
visible goal.

The gripper Door trial issues no rotation commands in any of its 40 decisions
and only two positive close commands, including the unexecuted final stop
response. Its hinge barely moves. This proves that the available rotational
degrees of freedom were unused; it does not prove rotation was strictly
necessary for this particular reset. The square-nut final image shows the nut
near the fingers and separate from the peg. Its sparse evaluator does not
record nut height or contacts, so the trace does not establish whether an
intermediate grasp was stable.

Hammer's nail-to-goal distance does not improve at any logged step, and its
final images show the hammer lying on the table outside the hand. Pen's final
images show the blue pen on the table, not retained in the hand; its goal
distance grows from a minimum 0.000390 m to a final 0.2929 m, while orientation
similarity never exceeds 0.2424. It stops at decision `013`, before exhausting
the decision budget. The can remains in the source bin in the final image.

Sources: [hand ball lift evaluation](hand_ball_lift/evaluation.json),
[hand relocation evaluation](hand_relocate/evaluation.json),
[hand Door evaluation](hand_door/evaluation.json),
[gripper Door trace](gripper_door/policy_trace.json),
[square-nut final image](gripper_nut_assembly_square/live.png),
[hammer evaluation](hand_hammer/evaluation.json),
[pen evaluation](hand_pen/evaluation.json),
[can final image](gripper_pick_place_can/live.png).

## Recorded observations

**Lift:** 40 validated decisions, 173 executed control steps, no native success
at any step. In calls `012`–`017`, Astra repeatedly requests downward movement
while measured end-effector height stays approximately 0.809–0.810 m. Calls
`024`–`032` repeat this plateau. The x/y command is zero throughout calls
`009`–`033`, despite the failed first grasp. At `018`, it closes; at `019`, it
raises the hand; at `020`, finger positions are approximately +0.002 and
−0.002 m, consistent with nearly empty closure. The external and wrist images
show the cube outside the intended grasp alignment and remaining on the table.
The final image still shows the cube on the table.

Sources: [Lift trace](gripper_lift/policy_trace.json),
[configuration](gripper_lift/config.json), [result](gripper_lift/result.json),
[final camera views](gripper_lift/live.png),
[annotated video](gripper_lift/annotated.mp4).

**Stack:** 40 validated decisions, 138 executed steps, no native success.
External-camera observations at calls `010`, `011`, `022`, and `032` show the
red cube remaining at essentially the same tabletop location while the hand
performs repeated close, lift, and sideways movements. Finger positions at
`011` and `022` are approximately ±0.0016 m, and at `032` approximately
±0.0013 m: almost fully closed, unlike a stable cube-width grasp. The final
image does not show the red cube on the green cube.

Sources: [Stack trace](gripper_stack/policy_trace.json),
[configuration](gripper_stack/config.json), [result](gripper_stack/result.json),
[final camera views](gripper_stack/live.png),
[annotated video](gripper_stack/annotated.mp4).

Both trials return `done=true` at call `039`, alongside nonzero actions:
Lift requests positive z=0.6 for 10 ticks; Stack requests
`[0.18, 0.25, 0.12, 0, 0, 0, -1]` for 10 ticks. Under the recorded runner
contract, **done means stop immediately; that action is not executed**.
Thus the final requested movement is discarded. This does not explain the
preceding repeated unsuccessful grasps and does not establish that executing
the final command would have succeeded.

## Comparison with earlier successful Lift trials

The [earlier gripper pilot](../gripper-pilot/README.md) contains two successful
Lift episodes initialized from recorded demonstration states, episodes 0 and 1.
The new Lift trial uses a fresh native seed-0 reset, not either recorded state.
The first older success begins at control step 36 and persists for the final
14 steps. During the held lift, finger positions remain near +0.025/−0.024 m
while end-effector height rises from approximately 0.824 to 0.942 m.
This is visibly and numerically different from the nearly empty closures in
the new trials.

Other recorded differences are 256×256 versus 512×512 camera images; changed
instruction wording; expanded action documentation distinguishing base-frame
commands from world-frame robot FK; a newly supplied remaining-control budget;
and limits of 30 versus 40 decisions and 300 versus 800 control steps. Recorded
action names, normalized bounds, translation/rotation scales, and 0.05-second
control interval agree. The old and new runs are not a controlled comparison:
none of those individual differences can be assigned causal responsibility.

## Interpretation and limits

The image and encoder evidence supports failed grasp alignment and ineffective
recovery after empty closure. Repeated downward commands with almost unchanged
height are consistent with obstruction/contact, but the published gripper
evaluation does not include contact diagnostics, so a specific contact cause
is not established. The traces do not demonstrate an actuator-format mismatch.

A future controlled investigation could repeat the same initial state while
changing one interface element at a time, and clarify the stop-without-action
contract. Those are hypotheses and proposed checks, not changes made to these
trials. Full-resolution per-call camera PNGs remain in the local run
directories; the published videos show the observations and executed commands.

## Interface and experiment limits supported by code and logs

**Control time is short despite long inference time.** Hand ticks are 0.01 s,
gripper ticks 0.05 s. Forty hand decisions with at most 20 repeats allow at most
8 s of physics; the final stop response reduces the completed hand trials to
7.8 s for the four hand trials using all decisions; pen stops at 2.6 s.
Forty gripper decisions with at most 10 repeats allow at most 20 s even
though the configured step ceiling is 800 (40 s). The decision limit binds
first. Model inference pauses physics, so a 12-minute wall-clock trial is not
12 minutes of manipulation. Short simulated time is a real constraint; that
more time alone would repair failed alignment is unproven.

**Stop semantics waste the final opportunity in these trials.** Nine baseline
runs stop on decision `039`, and pen on decision `013`, with a nonzero action. The prompt says
that done means stopping but does not explicitly say that the accompanying
action is discarded. This is a documented interface ambiguity worth testing.
The runner's behavior is consistent and its success report does not mistake
done for success.

**Temporal evidence is restricted.** Each Codex call starts fresh and receives
only current images/current proprioception plus its last eight action JSON
objects. It receives no previous images, previous proprioception, previous
reasoning, or previous evaluator feedback. Therefore statements such as "use
visual feedback and previous actions" do not provide a direct before/after
measurement pair. The missing measurement history is a concrete interface
limitation; its contribution to failure requires an ablation. It was also
present in the successful older pilot.

**Commands specify controller targets, not guaranteed physical displacement.**
Panda commands use base-frame OSC deltas with a 0.05 m translation scale, but
actual motion depends on controller response and collisions. For example,
Lift's first five ticks request z=−0.6 each while measured z changes from
1.01004 to 0.97534 m (3.47 cm), not five times 3 cm. Later downward commands
produce virtually no vertical movement. The documented scale is not a
promise of achieved translation. All 40 decisions in each completed gripper
task leave the three rotation commands zero. The model is not exploring all
available controls.

**The hand has a much harder low-level command space.** Ball tasks require
30 simultaneous normalized servo commands; Door uses 28. Recorded static
actuator documentation correctly supplies the 2.5 arm equilibrium gain,
finger gain 1, and local-to-world translation axes. A normalized zero means
the actuator-range midpoint, not hold-current-position. This experiment
therefore requires the model to coordinate motor commands and contact from
pixels, rather than merely choose a grasp location. No evidence here shows
that the corrected interface repeats the old arm-axis/gain error.

**Camera visibility and calibration differ.** Hand views include static
intrinsic/extrinsic calibration, while gripper prompts contain camera names
but no comparable camera matrices or base-to-world transform. The gripper
wrist image moves with the hand; pixel displacement alone is consequently
ambiguous. The final hand ball-lift front view has substantial forearm
occlusion, although the oblique view still shows the ball. The gripper Door
view shows its door nearly edge-on; its wrist view gives another perspective.
These are visible limitations, not proof that any camera setting caused the
failures. More pixels alone did not ensure success in the two new cube tasks.

## Minimal controlled follow-ups

1. Re-run the original successful Lift initialization (dataset episode 0)
   with its original prompt, image size, and budget, then the current interface
   on that same state. Keep simulator/controller/model request fixed and
   repeat seeds/calls before interpreting stochastic variation. This isolates
   interface/reset differences better than switching everything at once.
2. On the same starting state, compare current-only sensing with one previous
   image/proprioception pair plus the intervening command. Preserve the same
   allowed sensor boundary; do not introduce object pose or evaluator feedback.
3. Clarify stop-without-action explicitly, or test execute-then-stop as a
   separately versioned interface. Record requested versus executed repeat
   counts and compare at equal executed-time/decision budgets.
4. Compare equal simulated-time budgets and equal decision budgets separately.
   A longer-budget hand Door run is informative because its measured hinge
   already reaches 61.6°, but should not be reported as guaranteed success.
5. Use a different simulator/dataset as an additional, separately labeled
   experiment with a simple visually identifiable target and comparable
   camera/proprioception boundary. First verify neutral/control calibration
   and a known successful reference rollout without exposing reference actions
   to Astra. A successful easier task would establish capability under that
   interface; it would not by itself diagnose these contact-rich failures.

No running simulator, policy, instruction, or evaluation criterion was changed
as part of this diagnosis.

## Separate PyBullet reach success: independently verified

The separate `runs/bullet-pilot/bullet_reach` seed-0 trial succeeded after one
model decision and three simulator steps. A fresh reset plus replay of exactly
the recorded action verified that it did **not** start successful: initial
end-effector-to-target distance was 0.197590 m against a 0.05 m native threshold.
The command `[0.015, -0.45, -1.0]`, `repeat=3`, `done=false` produced distances
0.168716, 0.107171, and 0.047495 m, matching the original log exactly. The third
step crossed the success threshold and the environment terminated.

The adapter's policy observation contains robot joint positions/velocities,
end-effector pose/velocity, finger width, and two fixed calibrated RGB views.
Desired and achieved task goals are queried separately for evaluation; neither
is inserted into the policy observation. The replay accessed those goals only
for this post-trial audit.

Seeds 1 and 2 were independently reset and replayed as well: their initial
distances were 0.207950 and 0.133946 m, and final distances were 0.033271 and
0.025796 m. Both were initially unsuccessful and reached success after one
decision/three steps. All three seeds have distinct target positions and
different recorded commands; replay reproduces every evaluation row exactly.
The [machine-readable audit](../bullet-pilot/reach_audit.json) records the
initial geometry and per-step distances, exclusively for evaluation.

These are real threshold crossings, but seed 0's final position is only 2.51 mm
inside a 5 cm tolerance. They establish three successful three-coordinate
reaching commands, not successful grasping, dexterous manipulation, or proof
that PyBullet is inherently better. Simulator, task difficulty, controller,
camera interface, and stop documentation differ simultaneously from baseline.

## Separate PyBullet pick-and-place success: grasped transport verified

The seed-3 PyBullet pick-and-place trial succeeds after ten decisions and 25
control steps. An independent reset and exact action replay reproduces all 25
evaluation rows exactly. Initial object-to-goal distance is 0.170753 m, outside
the 0.05 m success threshold. Final distance is 0.015993 m: the object center
rises from 0.020 m to 0.181082 m, close to the target height of 0.180255 m.

Evaluator-only contact checks identify contact with both named robot fingers
at every sampled control step from 9 through 25. Final finger width is
0.04018 m. Together with the rising object trajectory and final RGB images,
this supports a grasped transport into the goal region, not a free-flight
threshold crossing. The [pick-and-place audit](../bullet-pilot/pick_place_audit.json)
records these checks; none were available to the policy during control.

The native environment terminates immediately on first success. This trial
therefore does not establish a sustained goal hold, release, or stable placed
object. It is meaningful contact-manipulation evidence beyond simple reaching,
but one trial with a fixed-orientation four-action controller cannot establish
that a different simulator alone solves the earlier failures. The original
Panda interface exposed seven pose/gripper coordinates; Adroit exposed many
more native joint controls. Dataset, task, controller, and observation changes
remain confounded.

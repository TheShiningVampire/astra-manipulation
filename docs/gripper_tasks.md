# Five gripper tasks

`GripperTaskEnvironment` supports `lift`, `stack`, `door`,
`nut_assembly_square`, and `pick_place_can`. Each uses the native robosuite
1.5.1 task and success predicate, a Panda parallel gripper, external and wrist
RGB cameras (512 pixels by default), and a 20 Hz OSC pose controller.

The model sees only pixels, an explicit task instruction, and the existing
robot-encoder/FK whitelist. Object positions, target coordinates, contact state,
reward, and native success remain evaluator-only. Commands are seven normalized
values: six **base-frame delta** pose coordinates and one gripper command.
Translation is scaled by 0.05 m and rotation by 0.5 rad; gripper -1 opens and +1
closes. A zero pose delta holds the current controller target.

PickPlaceCan includes one disclosed visual modification: a bright green,
non-colliding rectangular frame marks the native can destination compartment.
The marker is a fixed task fixture, does not follow object motion, and does not
alter collision geometry or success criteria. Its purpose is to make the
otherwise implicit object-to-compartment assignment visible in camera pixels.
Door's external camera uses a fixed wider workspace calibration, and the can
task uses a wider field of view, so their handles and destination compartments
are visible. Neither camera tracks simulated objects.

All five support deterministic native resets through an explicit seed.
Only Lift supports recorded robomimic episode initial states; providing a
dataset or recorded episode to another task raises an error. Other tasks are
fresh simulator trials and must not be described as demonstration replays.

Implementation references are the installed robosuite 1.5.1 `OSC_POSE`
controller configuration, `environments/manipulation/{lift,stack,door,
nut_assembly,pick_place}.py`, and their native `_check_success` methods.

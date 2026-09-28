# Five dexterous-hand tasks

`HandTaskEnvironment(task, instruction=None, dataset_path=None, max_steps=600, image_size=768)` provides five distinct objectives through the shared observation/action interface.

| Task | Controls | Objective and evaluator |
|---|---:|---|
| relocate | 30 | Carry ball into visible green region; native center-to-target distance <0.10 m |
| door | 28 | Unlatch and open door; native hinge angle ≥1.35 rad |
| hammer | 26 | Use hammer to drive nail; native nail-to-goal distance <0.01 m |
| pen | 24 | Reorient held blue pen to green reference; native position distance <0.075 m and orientation dot product >0.95 |
| ball_lift | 30 | Raise ball center above z=0.10 m for five consecutive control steps, tabletop z=0 |

The first four tasks use [Gymnasium-Robotics Adroit](https://robotics.farama.org/envs/adroit_hand/) environments. The fifth is an explicit custom evaluator on Relocate's physics: it measures lifting instead of target relocation, and hides the green goal marker. It is a distinct objective but not an independent robot or physics asset. It does not assert stable grasp or finger contact: an object held above threshold for the specified duration satisfies its definition.

Relocate and ball_lift support recorded initial states from the converted official hand_dapg JSON via `dataset_path` and `episode_id`. Door, hammer and pen use seeded benchmark resets; the framework does not claim those are downloaded dataset episodes. If an unsupported recorded episode reset is requested, the adapter fails explicitly.

## Robot sensing and control

No native task observation vector is passed to the policy. Each actuator transmission resolves its associated scalar joint. The adapter checks unit gear, robot actuator name, and ancestry under the robot `forearm` body. It then gathers qpos and qvel at that joint's actual addresses. In particular Door's native observation omits a robot coordinate, so taking a raw observation prefix would be incorrect. Different tasks have different arm mobility: Door has one translation and three arm rotations; Hammer has two arm rotations; Pen has no free arm coordinates. All include the corresponding 24 wrist/finger controls.

The policy also sees the robot `S_grasp` palm site's world position and orientation, obtainable by robot forward kinematics. Object positions, goal displacements, contact state, rewards and success stay inside evaluator output. Finger and wrist controls are listed by actual actuator name; arrays follow that same order.

Control normalization and loaded gain/bias values are exported from each instantiated model, after the environment's actuator modifications. The prompt explicitly states `u=midpoint+action*halfwidth` and `force=gain*u+constant_bias+position_bias*q+velocity_bias*qdot`. The no-load equilibrium is derived from these values, not assumed to equal control. Real equilibrium depends on gravity, contacts, passive forces and limits. Translation units are meters and hinge units radians. Static world directions are derived for each existing slide joint. For the world-rooted Adroit arm, local X points almost world -X, local Y almost world +Z/up, local Z almost world +Y/horizontal. Missing axes are not controllable. See [action-space audit](action_space_audit.md) for the earlier description error and corrected derivation.

## Cameras

Two independent 768×768 RGB images (`front`, `oblique`) use fixed world camera presets. Look-at points, azimuths, elevations and distances are chosen by task before reset and never depend on hidden object positions. The oblique Door view uses a wider predetermined distance to include the door. Neither camera tracks bodies. Perspective intrinsics and camera center/forward/up vectors are exported as static calibration. Each image is the raw rendered sensor image; evaluator geometry and success labels are not burned into the model input.

All five tasks were smoke-tested under OSMesa for reset, rendering, stepping and close. Both views of each task were visually inspected: the robot and relevant task objects are visible, with complementary views mitigating occlusion. These are rendered fixed external cameras; their availability is an experimental sensor configuration, not a claim about a particular real robot's camera layout.

Tests verify each real model's actuator/joint mapping and dimensions, exclusion of nonrobot state using noncontiguous address sentinels, and the custom lift evaluator's five-step hold and reset behavior.

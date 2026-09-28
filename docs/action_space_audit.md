# Adroit action-space audit

The original policy description was incorrect for the first six Adroit actuators. It described scaled controls as literal joint-position targets and did not identify the rotated arm translation frame. Earlier hand trials therefore have a material action-description confound and are not a fair baseline of Astra's control capability. The corrected interface is marked `adroit-actuator-audit-v2`. Physics, actuator parameters, normalization and command execution remain unchanged.

The audit inspected the instantiated `AdroitHandRelocate-v1` model from gymnasium-robotics 1.4.2 with MuJoCo 3.3.7, including the gain/bias values after the environment constructor modifies the wrist and finger actuators. This matters because reading XML alone does not capture all effective gains.

## Normalized action to actuator force

For each action `a` in `[-1,1]`, the environment applies:

```
u = (control_low + control_high)/2 + a * (control_high - control_low)/2
actuator_force = gain*u + constant_bias + position_bias*q + velocity_bias*qdot
```

All 30 actuators use unit joint transmission gear. Their constant and velocity biases are zero. Ignoring contact, gravity, passive forces, force saturation and joint limits, setting actuator force to zero gives `q_equilibrium = -gain/position_bias * u`. This is a no-load approximation, not a guaranteed equilibrium under actual loads.

| Actuator indices | Names | Gain | Position bias | No-load equilibrium |
|---|---|---:|---:|---|
| 0–5 | A_ARTx/y/z, A_ARRx/y/z | 500 | -200 | `q = 2.5*u` |
| 6–7 | A_WRJ1, A_WRJ0 | 10 | -10 | `q = u` |
| 8–29 | Finger actuators | 1 | -1 | `q = u` |

Consequently an approximate zero-actuator-force hold command uses `u=q/2.5` for arm coordinates, not `u=q`. Normalization back to `a` then uses that actuator's control range. The new spec labels these ranges `control_ranges`; it removes the misleading `joint_target_ranges` label and supplies actual joint coordinate limits separately. The first three controls have ranges `[-0.25,0.25]`, `[0,0.2]`, `[-0.3,0.5]`; the next three each have `[-0.75,0.75]`. Normalized zero is the midpoint control, not a no-motion command.

## Arm translation frame

The `forearm` body is directly attached to the world with fixed quaternion `[0.00056331217, -0.00056286377, 0.70682495699, 0.70738804488]` in MuJoCo's wxyz order. Multiplying its rotation matrix by the three local slide axes gives:

| Positive joint coordinate | World direction XYZ | Plain description |
|---|---|---|
| ARTx | `[-0.9999987317, 0.0000012683, -0.0015926524]` | Almost world -X, horizontal |
| ARTy | `[-0.0015926529, -0.0007963257, 0.9999984147]` | Almost world +Z, upward |
| ARTz | `[0, 0.9999996829, 0.0007963267]` | Almost world +Y, horizontal |

These slide axes precede the arm hinge joints in the kinematic chain and remain fixed in world coordinates. The arm rotation coordinates are local rotations; later hinge axes depend on earlier joint rotations. In particular, commanding local Z translation as though it were world height moves the hand horizontally.

## Observation and actuator indexing

The audit checked all 30 actuator transmissions against the model's joint qpos and dof addresses. They match indices 0 through 29 exactly:

```
0–5:   ARTx ARTy ARTz ARRx ARRy ARRz
6–7:   WRJ1 WRJ0
8–11:  FFJ3 FFJ2 FFJ1 FFJ0
12–15: MFJ3 MFJ2 MFJ1 MFJ0
16–19: RFJ3 RFJ2 RFJ1 RFJ0
20–24: LFJ4 LFJ3 LFJ2 LFJ1 LFJ0
25–29: THJ4 THJ3 THJ2 THJ1 THJ0
```

The policy now also receives the 30 robot joint velocities and the robot palm's `S_grasp` site position and rotation matrix in world coordinates. This site is rigidly attached to the robot: its pose is forward kinematics from robot encoders and known geometry. The matrix is row-major; its columns are the palm-site local axes expressed in world coordinates. This adds no object, target, contact, reward or success information. Static control metadata likewise describes only the embodiment.

Verification: corrected reset/render and sensor shapes passed; an independent finite difference of robot palm FK under each translation matched the static world-axis mapping to numerical precision. The three sensor-boundary tests pass, including exclusion of object velocity entries and every site except the robot palm. Original human action replay still establishes task feasibility; its actuator execution path has not changed.

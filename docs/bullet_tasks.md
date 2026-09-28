# Alternative simulator: PyBullet Panda

This comparison uses `panda-gym==3.0.7` and `pybullet==3.2.7` on CPU. It is a different simulator and task implementation, not a new recorded demonstration dataset. The executable benchmarks require no pretrained policy or expert action generator. [Official repository](https://github.com/qgallouedec/panda-gym), [environment documentation](https://panda-gym.readthedocs.io/en/latest/usage/environments.html), and [rendering documentation](https://panda-gym.readthedocs.io/en/latest/usage/advanced_rendering.html) describe the supported environments and headless rendering. The project uses the MIT license.

`BulletTaskEnvironment("bullet_reach")` runs native `PandaReach-v3`: move the blocked, closed gripper's end effector into a visible target sphere. It accepts three controls. `BulletTaskEnvironment("bullet_pick_place")` runs native `PandaPickAndPlace-v3`: move the green cube's center to a target cube, accepting three arm controls plus one finger-width control. Both use native success distance <0.05 m and terminate automatically when successful.

The native PickAndPlace goal can be on the tabletop: seed 0 produces such a goal, so native success in that configuration does not prove lifting or grasping. An elevated-goal seed can isolate the grasp-and-lift requirement more clearly, but seed choice must be reported rather than silently changing the benchmark. Even an elevated goal's position-based success predicate does not itself certify a stable grasp. Default reset seed is 0; recorded episode indices and dataset paths are explicitly unsupported.

The initial comparison selects Reach seed 0 and PickAndPlace seed 3. Seed 3 was selected before model trials because its target center is 0.18025 m above the tabletop, requiring substantial object elevation to satisfy the 0.05 m tolerance. This numerical check was evaluator-only; the model sees the target through the cameras, not its simulator coordinates. Both runs use medium reasoning, 768-pixel views, at most 40 decisions/800 simulator steps and at most 10 repeated steps per decision.

## Exact installed control interface

After the first reach completed successfully, seeds 1 and 2 were selected together for two additional reach trials with identical budgets; both are retained regardless of outcome. These repetitions remain a small diagnostic sample, not a general success-rate estimate.

Inspection of the installed 3.0.7 [`Panda` implementation](https://github.com/qgallouedec/panda-gym/blob/v3.0.7/panda_gym/envs/robots/panda.py) confirms that `action[:3] * 0.05` meters is added to the measured end-effector position in world coordinates. +Z is upward. Native inverse kinematics holds downward orientation, quaternion xyzw `[1,0,0,0]`; target height is clipped at z=0. The comparison therefore changes both physics and control abstraction relative to seven-value robosuite OSC and high-dimensional Adroit controls. It cannot isolate simulator choice as the sole cause of any success difference.

The fourth action, when available, requests a total finger-width increment of `action[3] * 0.2` meters. **Positive opens, negative closes**, the opposite sign convention from the robosuite gripper. Zero requests the measured width. Joint limits and motor dynamics affect realized motion. Twenty physics substeps at 1/500 s give a 0.04 s control interval. Repeating a displacement action applies a fresh increment each step.

The static action specification now explicitly states that `done=true` stops immediately and discards the action in that same response. A model should keep `done=false` when requesting any movement, including final approach. The runner's execution behavior is unchanged; this is an explicit wording improvement over earlier baseline prompts and must be treated as a comparison confound.

## Sensing and rendering

The native environment observation is not safe to forward: it concatenates robot measurements with exact object pose/velocity and returns `desired_goal` and `achieved_goal`. The adapter discards that entire observation and queries only robot joint positions/velocities, end-effector pose/velocity and finger width. [Robot-task source](https://github.com/qgallouedec/panda-gym/blob/v3.0.7/panda_gym/envs/core.py) defines the native privileged fields. Native task distance, object height, rewards and success remain evaluator-only and never enter policy requests.

Two fixed 768×768 calibrated perspective views are rendered directly with `ER_TINY_RENDERER` in Bullet DIRECT mode. Static view/projection matrices and intrinsics are supplied to the policy, along with camera position/forward/up vectors. No camera tracks the object or target. The target's visual material is changed to opaque magenta so the CPU renderer can distinguish it clearly from the solid green cube; target position, collisionlessness, physics and success definition are unchanged. Both tasks' reset images were visually inspected and the marker is visible in both views. Previews are saved locally under `runs/bullet-smoke/`.

Both tasks passed reset/render/step/close smoke tests. Boundary tests forbid all native task/goal observation calls while constructing the policy observation, verify the exact Cartesian scale and fixed orientation, and check camera calibration is static across seeds. No expert or scripted controller is used in Astra experiments.

## Reproduce

```bash
uv pip install --python .venv/bin/python -e '.[bullet]'
.venv/bin/python -m astra_manipulation.cli --task bullet_reach --seed 0 \
  --max-calls 40 --max-steps 800 --max-repeat 10 --request-retries 1 \
  --output runs/bullet-reach-new
.venv/bin/python -m astra_manipulation.cli --task bullet_pick_place --seed 3 \
  --max-calls 40 --max-steps 800 --max-repeat 10 --request-retries 1 \
  --output runs/bullet-pick-new
```

The recorded trials are in the [comparison report](../reports/bullet-pilot/README.md). Local annotated MP4s are copied to `exports/bullet-videos/` and bundled in `exports/astra-bullet-videos.zip`. Native success ends an episode immediately: success does not certify a long sustained hold or release-and-place maneuver.

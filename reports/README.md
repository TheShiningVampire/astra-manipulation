# Pilot results and interpretation

The [two gripper trials](gripper-pilot/README.md) both achieved the built-in Lift success condition using Astra's commands.

The [initial hand trials](hand-medium-interrupted/README.md) are **confounded by an incorrect action-space description** and interrupted by 240-second model-call timeouts. They must not be treated as a clean estimate of Astra's dexterous manipulation ability. The native commands were executed as specified by the simulator, but the prompt incorrectly described arm controls as literal joint-position targets and failed to explain the rotated forearm axes. This issue was found while investigating the user's observation that the hand did not approach the ball.

In this pinned Adroit model, the first six actuators use `force = 500 * control - 200 * joint_position`, before other physical forces. Therefore the no-load equilibrium is approximately `2.5 * control`, not `control`. The forearm frame is also rotated relative to world axes. See the [action-space audit](../docs/action_space_audit.md) for the correction and verified mappings.

An additional low-reasoning trial using the old description was deliberately stopped after 8 executed decisions / 44 control steps when the interface problem was discovered. Its ninth request was interrupted; it is not counted as a completed trial.

The separate [original-human-action replay](../docs/replay_validation.json) succeeds on both hand initializations. It establishes that these tasks are achievable in the simulator, but it does not validate the old prompt's description and never supplies actions to Astra.

The gripper prompts differ in wording and initialization. These few trials do not isolate paraphrase robustness or establish a general language-following success rate. Early setup checks (neutral smoke tests, a one-call connectivity check, and two failed Codex configuration checks) are excluded from task results. Full task traces are included in the linked directories.

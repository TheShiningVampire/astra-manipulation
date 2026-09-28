# Exploratory Astra trials

These recorded trials are a pilot, not a statistically reliable success-rate estimate. Errors are interrupted trials, not completed task failures.
Model: requested `gpt-6-astra` via Codex CLI. No privileged task state in model inputs.

| Trial | Outcome | Calls | Control steps | Wall seconds |
|---|---|---:|---:|---:|
| [astra-hand-episode0](astra-hand-episode0/result.json) | Interrupted (error) | 14 | 125 | 562.0 |
| [astra-hand-paraphrase1](astra-hand-paraphrase1/result.json) | Interrupted (error) | 18 | 93 | 431.5 |

Each trial includes a simulation-time MP4, sensor inputs, actuator commands, and separate evaluator data.
Task instructions and initializations differ; this is not a controlled comparison of embodiments or paraphrases.

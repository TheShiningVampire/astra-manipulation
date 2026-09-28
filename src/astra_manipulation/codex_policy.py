"""Use the installed Codex CLI's existing login without accessing credentials."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from PIL import Image
from .core import action_schema, validate_action
from .policy import SYSTEM, prompt_payload


class CodexPolicy:
    def __init__(self, model="gpt-6-astra", reasoning="medium", max_repeat=10, timeout=240):
        self.model, self.reasoning, self.max_repeat = model, reasoning, max_repeat
        self.timeout = timeout

    def act(self, observation, spec, history):
        # Empty working directory: no dataset, code, evaluation, or prior session.
        with tempfile.TemporaryDirectory(prefix="astra-observation-") as directory:
            root = Path(directory)
            schema = root / "action.schema.json"
            schema.write_text(json.dumps(action_schema(len(spec["low"]), self.max_repeat)))
            output = root / "action.json"
            command = ["codex", "exec", "--ignore-user-config", "--ephemeral",
                       "--skip-git-repo-check", "--sandbox", "read-only", "--json",
                       "--model", self.model, "--cd", directory,
                       "--output-schema", str(schema), "--output-last-message", str(output),
                       "-c", 'approval_policy="never"', "-c", 'web_search="disabled"',
                       "-c", "project_doc_max_bytes=0", "-c", "mcp_servers={}",
                       "-c", f'model_reasoning_effort="{self.reasoning}"']
            # Explicitly disable outside-information tools, plugins, and memory.
            for feature in ["shell_tool", "unified_exec", "apps", "plugins", "memories",
                            "multi_agent", "multi_agent_v2", "browser_use", "computer_use",
                            "image_generation", "view_image", "skill_search", "hooks",
                            "code_mode"]:
                command.extend(["-c", f"features.{feature}=false"])
            for index, (name, pixels) in enumerate(observation.images.items()):
                path = root / f"camera_{index}.png"
                Image.fromarray(pixels).save(path)
                command.extend(["--image", str(path)])
            command.append("-")
            prompt = SYSTEM + "\nUse no tools. Images are attached in camera_names order.\n" + json.dumps(
                prompt_payload(observation, spec, history))
            environment = dict(os.environ)
            # Don't propagate parent thread identity into a fresh control call.
            for key in ("CODEX_THREAD_ID", "CODEX_SESSION_ID"):
                environment.pop(key, None)
            start = time.monotonic()
            try:
                result = subprocess.run(command, input=prompt, text=True, capture_output=True,
                                        env=environment, timeout=self.timeout)
            except subprocess.TimeoutExpired as exc:
                raise TimeoutError(f"Astra did not return an action within {self.timeout} seconds; no action executed") from exc
            if result.returncode:
                raise RuntimeError(f"Codex failed ({result.returncode}): {result.stderr[-3000:]}")
            events = []
            for line in result.stdout.splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            # Fail closed if this CLI version offers/executes any unexpected tools.
            for event in events:
                item = event.get("item", {})
                if item.get("type") == "error":
                    raise RuntimeError("Codex reported an error: " + json.dumps(item))
                if item and item.get("type") not in {"reasoning", "agent_message"}:
                    raise RuntimeError("Observation isolation violated: unexpected Codex item " + str(item.get("type")))
                if event.get("type") in {"error", "turn.failed"}:
                    raise RuntimeError(f"Codex model call failed: {event}")
            if not output.exists():
                raise RuntimeError("Codex returned no structured action")
            action = validate_action(json.loads(output.read_text()), spec, self.max_repeat)
            usage = next((e.get("usage") for e in reversed(events) if e.get("type") == "turn.completed"), None)
            return action, {"requested_model": self.model, "resolved_model": None,
                            "model_verification": "CLI --model flag; server model ID not exposed in JSON events",
                            "provider": "codex-cli", "usage": usage,
                            "latency_seconds": time.monotonic() - start,
                            "tool_calls": 0}

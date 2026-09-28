import base64
import io
import json
import os
import time
from PIL import Image
from .core import action_schema, validate_action

SYSTEM = """You control a simulated robot directly. Your only observations are the attached
robot camera images and measured robot proprioception. Follow the user's task instruction.
Return actuator commands under the supplied action specification, not a plan or code.
There is no hidden perception, grasp planner, expert policy or task skill executing for you.
Use visual feedback and your previous actions to correct motion. done means you choose to stop;
it does not determine evaluator success. Do not infer that a previous action succeeded without
checking the images. Respond with the exact requested JSON schema."""


def prompt_payload(observation, spec, history):
    return {"observation": observation.text(), "action_specification": spec,
            "previous_actions": history[-8:]}


class AstraPolicy:
    def __init__(self, model="gpt-6-astra", reasoning="medium", max_repeat=10, timeout=240):
        from openai import OpenAI
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for --provider api")
        self.timeout = timeout
        self.client = OpenAI(timeout=timeout, max_retries=1)
        self.model, self.reasoning, self.max_repeat = model, reasoning, max_repeat

    def act(self, observation, spec, history):
        content = [{"type": "input_text", "text": json.dumps(prompt_payload(observation, spec, history))}]
        for name, pixels in observation.images.items():
            buffer = io.BytesIO()
            Image.fromarray(pixels).save(buffer, format="PNG")
            content.extend([{"type": "input_text", "text": "Camera: " + name},
                {"type": "input_image", "image_url": "data:image/png;base64," +
                 base64.b64encode(buffer.getvalue()).decode(), "detail": "high"}])
        start = time.monotonic()
        response = self.client.responses.create(model=self.model, instructions=SYSTEM,
            input=[{"role": "user", "content": content}], reasoning={"effort": self.reasoning},
            max_output_tokens=4096, store=False,
            text={"format": {"type": "json_schema", "name": "robot_action", "strict": True,
                             "schema": action_schema(len(spec["low"]), self.max_repeat)}})
        action = validate_action(json.loads(response.output_text), spec, self.max_repeat)
        return action, {"model": response.model, "response_id": response.id,
                        "latency_seconds": time.monotonic() - start,
                        "usage": response.usage.model_dump() if response.usage else None}


class NeutralPolicy:
    """Pipeline smoke test only; never counted as an Astra trial."""
    def act(self, observation, spec, history):
        return {"action": [(lo + hi) / 2 for lo, hi in zip(spec["low"], spec["high"])],
                "repeat": 1, "done": False}, {"model": "neutral-smoke-test", "usage": None}

from dataclasses import dataclass
import math
import numpy as np


@dataclass(frozen=True)
class Observation:
    images: dict[str, np.ndarray]
    proprioception: dict[str, list[float]]
    instruction: str
    step_index: int

    def text(self):
        # Deliberately no generic simulator observation/info dictionary.
        return {"instruction": self.instruction, "step_index": self.step_index,
                "proprioception": self.proprioception, "camera_names": list(self.images)}


def action_schema(dimension: int, max_repeat: int = 10):
    return {"type": "object", "properties": {
        "action": {"type": "array", "items": {"type": "number"},
                   "minItems": dimension, "maxItems": dimension},
        "repeat": {"type": "integer", "minimum": 1, "maximum": max_repeat},
        "done": {"type": "boolean"},
    }, "required": ["action", "repeat", "done"], "additionalProperties": False}


def validate_action(value, spec, max_repeat=10):
    if not spec["low"] or len(spec["low"]) != len(spec["high"]):
        raise ValueError("Invalid action specification dimensions")
    if any(not math.isfinite(lo) or not math.isfinite(hi) or lo > hi
           for lo, hi in zip(spec["low"], spec["high"])):
        raise ValueError("Invalid action specification bounds")
    if not isinstance(value, dict) or set(value) != {"action", "repeat", "done"}:
        raise ValueError("Action must have exactly action, repeat, done")
    action = value["action"]
    if not isinstance(action, list) or len(action) != len(spec["low"]):
        raise ValueError("Incorrect action dimension")
    for x, low, high in zip(action, spec["low"], spec["high"]):
        if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
            raise ValueError("Action must contain finite numbers")
        if x < low or x > high:
            raise ValueError("Action exceeds actuator limits; refusing to clip silently")
    if type(value["repeat"]) is not int or not 1 <= value["repeat"] <= max_repeat:
        raise ValueError("Invalid action repeat")
    if type(value["done"]) is not bool:
        raise ValueError("done must be boolean")
    return value

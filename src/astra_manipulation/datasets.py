"""Small, public robot demonstration downloads; never used as privileged policy state."""
from __future__ import annotations

import hashlib
import json
import os
import io
import pickle
from pathlib import Path
import urllib.request

LIFT_URL = "https://huggingface.co/datasets/robomimic/robomimic_datasets/resolve/main/v1.5/lift/ph/demo_v15.hdf5"
ADROIT_ID = "D4RL/relocate/human-v2"
ADROIT_RAW_URL = "https://raw.githubusercontent.com/aravindr93/hand_dapg/master/dapg/demonstrations/relocate-v0_demos.pickle"
ADROIT_RAW_SHA256 = "1ad6bbe10e9550865279a44540745eccd22ef623aa0c2e95d2baf5678b3a3284"


class _NumericNumpyUnpickler(pickle.Unpickler):
    """Only decode the three NumPy constructors present in the pinned author file."""
    def find_class(self, module, name):
        import numpy as np
        from numpy.core.multiarray import _reconstruct
        allowed = {("numpy", "dtype"): np.dtype, ("numpy", "ndarray"): np.ndarray,
                   ("numpy.core.multiarray", "_reconstruct"): _reconstruct}
        if (module, name) not in allowed:
            raise pickle.UnpicklingError(f"Disallowed pickle global: {module}.{name}")
        return allowed[module, name]


def download_adroit_initial_states(destination: str | Path) -> dict:
    """Convert hash-pinned original author demonstrations into numeric reset JSON."""
    import numpy as np
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    raw_path = destination / "relocate-v0_demos.pickle"
    if not raw_path.exists():
        temporary = raw_path.with_suffix(".download")
        urllib.request.urlretrieve(ADROIT_RAW_URL, temporary)
        temporary.replace(raw_path)
    content = raw_path.read_bytes()
    if hashlib.sha256(content).hexdigest() != ADROIT_RAW_SHA256:
        raise ValueError("Original Adroit pickle does not match the reviewed source hash")
    demonstrations = _NumericNumpyUnpickler(io.BytesIO(content)).load()
    episodes = []
    for demo in demonstrations:
        state = demo["init_state_dict"]
        clean = {}
        for key, shape in {"qpos": (36,), "qvel": (36,), "obj_pos": (3,), "target_pos": (3,)}.items():
            value = np.asarray(state[key], dtype=np.float64)
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError(f"Invalid reset state {key}")
            clean[key] = value.tolist()
        episodes.append(clean)
    path = destination / "adroit_relocate_initial_states.json"
    payload = {"dataset": "hand_dapg/relocate-v0", "source": ADROIT_RAW_URL,
               "source_sha256": ADROIT_RAW_SHA256, "episodes": episodes}
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return {"dataset": payload["dataset"], "path": str(path.resolve()),
            "episodes": len(episodes), "source_sha256": ADROIT_RAW_SHA256}


def download_lift(destination: str | Path) -> dict:
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "lift_ph_demo_v15.hdf5"
    if not path.exists():
        temporary = path.with_suffix(".download")
        urllib.request.urlretrieve(LIFT_URL, temporary)
        temporary.replace(path)
    import h5py
    with h5py.File(path, "r") as data:
        metadata = {"dataset": "robomimic/lift/ph/v1.5", "path": str(path.resolve()),
                    "url": LIFT_URL, "episodes": len(data["data"]),
                    "env_args": json.loads(data["data"].attrs["env_args"])}
    with path.open("rb") as handle:
        metadata["sha256"] = hashlib.file_digest(handle, "sha256").hexdigest()
    return metadata


def download_adroit(destination: str | Path) -> dict:
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    os.environ["MINARI_DATASETS_PATH"] = str(destination)
    import minari
    dataset = minari.load_dataset(ADROIT_ID, download=True)
    return {"dataset": ADROIT_ID, "path": str(destination / ADROIT_ID),
            "episodes": dataset.total_episodes, "steps": dataset.total_steps,
            "source": "https://minari.farama.org/datasets/D4RL/relocate/human-v2/",
            "reset_support": "fresh seeded simulator resets; recorded episode state restoration is not supported"}


def download_dataset(backend: str, destination: str | Path) -> dict:
    if backend in {"lift", "gripper", "robosuite"}:
        return download_lift(destination)
    if backend in {"adroit", "dexterous", "relocate"}:
        return download_adroit(destination)
    raise ValueError(f"Unknown dataset backend {backend!r}")


def export_adroit_samples(dataset_root: str | Path, destination: str | Path,
                          episode_id: int = 0, stride: int = 50) -> dict:
    """Export robot-only recorded inputs; reference actions go to a separate evaluator file.

    This is an offline proprioception diagnostic, not a vision-based closed-loop task.
    Minari stores neither camera frames nor full restorable state for this dataset.
    """
    if stride < 1:
        raise ValueError("stride must be positive")
    os.environ["MINARI_DATASETS_PATH"] = str(Path(dataset_root).resolve())
    import minari
    dataset = minari.load_dataset(ADROIT_ID)
    episode = dataset[episode_id]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    inputs, targets = [], []
    for step in range(0, len(episode.actions), stride):
        inputs.append({"step_index": step, "instruction": "Move the blue ball to the green target.",
                       "images": {}, "proprioception": {
                           "joint_positions": episode.observations[step, :30].tolist()}})
        targets.append({"step_index": step, "demonstration_action": episode.actions[step].tolist()})
    (destination / "policy_inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    (destination / "evaluator_reference_actions.json").write_text(json.dumps(targets, indent=2) + "\n")
    return {"dataset": ADROIT_ID, "episode_id": episode_id, "samples": len(inputs),
            "observation_mode": "proprioception_only", "privileged_dimensions_removed": 9,
            "limitation": "No recorded images; agreement is not task success, and object/goal information is unavailable."}

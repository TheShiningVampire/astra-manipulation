"""Task registry for the ten-task visual control pilot."""
from .gripper_tasks import GRIPPER_TASKS, GripperTaskEnvironment
from .hand_tasks import HAND_TASKS, HandTaskEnvironment


def list_tasks():
    from .bullet_tasks import BULLET_TASKS
    return {**{"gripper_" + key: value for key, value in GRIPPER_TASKS.items()},
            **{"hand_" + key: value for key, value in HAND_TASKS.items()}, **BULLET_TASKS}


def make_task(task, instruction=None, dataset_path=None, max_steps=600, image_size=None):
    if task.startswith("bullet_"):
        from .bullet_tasks import BulletTaskEnvironment
        return BulletTaskEnvironment(task, instruction, dataset_path, max_steps, image_size or 768)
    if task.startswith("gripper_"):
        return GripperTaskEnvironment(task.removeprefix("gripper_"), instruction,
            dataset_path, max_steps, image_size or 512)
    if task.startswith("hand_"):
        return HandTaskEnvironment(task.removeprefix("hand_"), instruction,
            dataset_path, max_steps, image_size or 768)
    raise ValueError(f"Unknown task {task!r}")

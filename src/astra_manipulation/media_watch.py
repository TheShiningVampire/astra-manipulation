"""Encode completed suite trials while remaining simulations continue."""
import argparse
import json
from pathlib import Path
import time

from .media import export_media
from .publish_suite import TITLES
from .suite import TASKS


def watch(root, output):
    root, output = Path(root), Path(output)
    completed, failed = set(), set()
    while len(completed | failed) < len(TASKS):
        for task in TASKS:
            if task in completed | failed or not (root / task / "result.json").exists():
                continue
            try:
                manifest = export_media(root / task, output / task, TITLES[task])
                print(json.dumps({"task": task, "media_ready": True,
                                  "gif_bytes": manifest["gif"]["bytes"]}), flush=True)
                completed.add(task)
            except Exception as exc:
                print(json.dumps({"task": task, "media_error": str(exc)}), flush=True)
                failed.add(task)
        time.sleep(3)
    if failed:
        raise SystemExit("Media failures: " + ", ".join(sorted(failed)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--output", default="reports/ten-task-pilot")
    args = parser.parse_args()
    watch(args.root, args.output)

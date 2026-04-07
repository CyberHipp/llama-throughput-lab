#!/usr/bin/env python3
"""Simple controller that prints queued augmentation tasks."""

from __future__ import annotations

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "registries" / "VORTEX_POST_QUEUE_AUGMENTATION_TASKS.tsv"


def iter_tasks() -> list[dict[str, str]]:
    with QUEUE.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    if not QUEUE.exists():
        print(f"missing registry: {QUEUE}")
        return 1

    tasks = iter_tasks()
    for task in tasks:
        print(f"{task['task_id']}: {task['state']} ({task['priority']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

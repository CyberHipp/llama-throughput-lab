#!/usr/bin/env python3
"""Simple controller that prints queued augmentation tasks."""

from __future__ import annotations

import csv

from tools.automation.runtime_state import resolve_runtime_registry_path

QUEUE_SEED = "registries/VORTEX_POST_QUEUE_AUGMENTATION_TASKS.tsv"


def iter_tasks() -> list[dict[str, str]]:
    queue_path = resolve_runtime_registry_path(QUEUE_SEED)
    with queue_path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    try:
        tasks = iter_tasks()
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    for task in tasks:
        print(f"{task['task_id']}: {task['state']} ({task['priority']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

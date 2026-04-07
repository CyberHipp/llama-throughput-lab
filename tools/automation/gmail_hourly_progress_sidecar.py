#!/usr/bin/env python3
"""Generate a tiny hourly progress summary from queue registry rows."""

from __future__ import annotations

import csv

from tools.automation.runtime_state import resolve_runtime_registry_path

QUEUE_SEED = "registries/VORTEX_POST_QUEUE_AUGMENTATION_TASKS.tsv"


def main() -> int:
    try:
        queue_path = resolve_runtime_registry_path(QUEUE_SEED)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    with queue_path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    total = len(rows)
    queued = sum(1 for r in rows if r.get("state") == "queued")
    print(f"tasks_total={total}")
    print(f"tasks_queued={queued}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

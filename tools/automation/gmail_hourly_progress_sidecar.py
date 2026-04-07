#!/usr/bin/env python3
"""Generate a tiny hourly progress summary from queue registry rows."""

from __future__ import annotations

from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "registries" / "VORTEX_POST_QUEUE_AUGMENTATION_TASKS.tsv"


def main() -> int:
    if not QUEUE.exists():
        print(f"missing registry: {QUEUE}")
        return 1

    with QUEUE.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))

    total = len(rows)
    queued = sum(1 for r in rows if r.get("state") == "queued")
    print(f"tasks_total={total}")
    print(f"tasks_queued={queued}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

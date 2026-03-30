#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

DENY_PATTERNS = ("eval(", "exec(", "pickle.loads(", "yaml.load(", "shell=True")
SCAN_DIRS = ("llama_nexus_lab", "throughput_lab", "scripts")


def main() -> int:
    violations: list[str] = []
    for folder in SCAN_DIRS:
        for path in Path(folder).rglob("*.py"):
            if path.name == "security_check.py":
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in DENY_PATTERNS:
                if pattern in text:
                    violations.append(f"{path}: contains forbidden pattern '{pattern}'")
    if violations:
        for row in violations:
            print(row)
        return 1
    print("security_check: no forbidden patterns detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Helpers for separating mutable automation registry state from committed seeds."""

from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_ROOT_ENV = "AUTOMATION_STATE_DIR"


def project_root() -> Path:
    override = __import__("os").environ.get("AUTOMATION_ROOT_DIR")
    return Path(override).resolve() if override else ROOT


def runtime_state_root() -> Path:
    root = project_root()
    override = __import__("os").environ.get(_RUNTIME_ROOT_ENV)
    return Path(override).resolve() if override else root / "artifacts" / "automation_state"


def resolve_runtime_registry_path(seed_relative: str) -> Path:
    root = project_root()
    seed_path = root / seed_relative
    if not seed_path.exists():
        raise FileNotFoundError(f"missing seed registry: {seed_path}")

    runtime_path = runtime_state_root() / seed_relative
    runtime_path.parent.mkdir(parents=True, exist_ok=True)
    if not runtime_path.exists():
        shutil.copyfile(seed_path, runtime_path)
    return runtime_path

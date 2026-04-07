#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llama_nexus_lab.email_turn_adapter import build_email_bundle, build_turn_packet, serialize_turn_packet
from llama_nexus_lab.gauntlet import (
    GauntletSpec,
    QueueItem,
    build_temp_runtime_config,
    load_gauntlet_spec,
    process_queue,
    save_gauntlet_spec,
    write_queue_manifest,
)

BASE_CONFIG = REPO_ROOT / "configs/nexus/default.json"
GAUNTLET_DIR = REPO_ROOT / "configs/nexus/gauntlets"
PRESET_DIR = REPO_ROOT / "configs/nexus/gauntlets/presets"
TUI_RUNS_DIR = REPO_ROOT / "artifacts/nexus/tui_runs"
QUEUE_DIR = TUI_RUNS_DIR / "queue"
EMAIL_TURNS_DIR = REPO_ROOT / "artifacts/nexus/email_turns"

MENU = [
    "1. New Gauntlet",
    "2. Load Gauntlet Preset",
    "3. Dry-Run Preview",
    "4. Launch One Run",
    "5. Enqueue Current Gauntlet",
    "6. Run Queue",
    "7. Show Recent Artifacts",
    "8. Generate Turn Packet (Email Chess Adapter)",
    "9. Exit",
]


def _prompt_bool(label: str) -> bool:
    value = input(f"{label} [y/n]: ").strip().lower()
    if value not in {"y", "n"}:
        raise ValueError(f"Invalid boolean input for {label}: '{value}'")
    return value == "y"


def _prompt_spec() -> GauntletSpec:
    gauntlet_name = input("gauntlet_name: ").strip()
    query = input("query: ").strip()
    max_search_intents_raw = input("max_search_intents: ").strip()
    if not max_search_intents_raw.isdigit() or int(max_search_intents_raw) <= 0:
        raise ValueError("max_search_intents must be a positive integer")

    spec = GauntletSpec(
        gauntlet_name=gauntlet_name,
        query=query,
        max_search_intents=int(max_search_intents_raw),
        strict_citation_required=_prompt_bool("strict_citation_required"),
        dry_run=_prompt_bool("dry_run"),
        require_verify_pass=_prompt_bool("require_verify_pass"),
    )
    spec.validate()
    return spec


def _preset_path(name: str) -> Path:
    return GAUNTLET_DIR / f"{name}.json"


def _load_library_preset(name: str) -> GauntletSpec:
    payload = json.loads((PRESET_DIR / f"{name}.json").read_text(encoding="utf-8"))
    if "query" not in payload:
        template = payload.get("query_template", "")
        topic = input("topic placeholder value: ").strip() or "default topic"
        payload["query"] = template.replace("{topic}", topic)
    spec = GauntletSpec(
        gauntlet_name=payload["gauntlet_name"],
        query=payload["query"],
        max_search_intents=int(payload["max_search_intents"]),
        strict_citation_required=bool(payload["strict_citation_required"]),
        dry_run=bool(payload["dry_run"]),
        require_verify_pass=bool(payload["require_verify_pass"]),
    )
    spec.validate()
    return spec


def build_launch_command(spec: GauntletSpec, runtime_config_path: str) -> list[str]:
    governed_path = REPO_ROOT / "scripts/run_nexus_governed_smoke.py"
    pipeline_path = REPO_ROOT / "scripts/run_nexus_pipeline.py"

    if spec.require_verify_pass:
        return [
            sys.executable,
            str(governed_path),
            "--query",
            spec.query,
            "--config",
            runtime_config_path,
            "--require-verify-pass",
        ]

    return [
        sys.executable,
        str(pipeline_path),
        "--query",
        spec.query,
        "--config",
        runtime_config_path,
    ]


def _build_runtime_config(spec: GauntletSpec) -> tuple[str, str]:
    run_id = f"tui-{uuid.uuid4().hex[:10]}"
    run_dir = TUI_RUNS_DIR / run_id
    config_path = run_dir / "config.json"
    build_temp_runtime_config(BASE_CONFIG, spec, config_path)
    return run_id, str(config_path)


def _show_recent_artifacts(limit: int = 5) -> list[str]:
    if not TUI_RUNS_DIR.exists():
        return []
    dirs = sorted([p for p in TUI_RUNS_DIR.iterdir() if p.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(path) for path in dirs[:limit]]


def _run_command(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    payload: dict = {}
    if result.stdout.strip():
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            payload = {"raw_stdout": result.stdout.strip()}
    payload["exit_code"] = result.returncode
    if result.stderr.strip():
        payload["stderr"] = result.stderr.strip()
    return payload


def _queue_run_item(item: QueueItem) -> dict:
    payload = _run_command(list(item.command))
    return {
        "run_id": payload.get("run_id"),
        "exit_code": payload.get("exit_code", 1),
        "reason": payload.get("verification_reason") or payload.get("stderr") or "run failed",
        "artifacts": payload.get("artifacts"),
    }


def _generate_turn_packet() -> dict:
    game_id = input("game_id: ").strip() or "default-game"
    turn_raw = input("turn: ").strip()
    if not turn_raw.isdigit() or int(turn_raw) <= 0:
        raise ValueError("turn must be a positive integer")
    move = input("move/action: ").strip()
    actor = input("actor: ").strip() or "operator"
    fen = input("state.fen (optional): ").strip() or "startpos"

    packet = build_turn_packet(
        game_id=game_id,
        turn=int(turn_raw),
        actor=actor,
        move=move,
        state={"fen": fen},
        legal_next=[],
    )
    out_dir = EMAIL_TURNS_DIR / game_id
    out_path = out_dir / f"turn_{int(turn_raw)}.json"
    attachment_path = serialize_turn_packet(packet, out_path)
    bundle = build_email_bundle(packet, attachment_path)
    return {
        "packet_path": attachment_path,
        "packet": packet,
        "email_bundle": bundle,
    }


def _render_menu() -> None:
    print("\nNEXUS TUI - VorteX research gauntlets")
    for row in MENU:
        print(row)


def _maybe_curses_menu() -> str:
    if not sys.stdin.isatty() or os.environ.get("TERM") in {None, "dumb"}:
        return input("Choose menu option [1-9]: ").strip()
    try:
        import curses
    except Exception:
        return input("Choose menu option [1-9]: ").strip()

    choice = {"value": "9"}

    def _inner(stdscr):
        curses.curs_set(0)
        current = 0
        while True:
            stdscr.clear()
            stdscr.addstr(0, 0, "NEXUS TUI - VorteX research gauntlets")
            for idx, row in enumerate(MENU):
                prefix = "> " if idx == current else "  "
                stdscr.addstr(idx + 2, 0, prefix + row)
            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                current = (current - 1) % len(MENU)
            elif key in (curses.KEY_DOWN, ord("j")):
                current = (current + 1) % len(MENU)
            elif key in (10, 13):
                choice["value"] = str(current + 1)
                break
        return 0

    curses.wrapper(_inner)
    return choice["value"]


def _print_summary(summary: dict) -> None:
    print(json.dumps(summary, sort_keys=True))


def main() -> int:
    spec: GauntletSpec | None = None
    queue: list[QueueItem] = []

    while True:
        _render_menu()
        action = _maybe_curses_menu()

        try:
            if action == "1":
                spec = _prompt_spec()
                save_gauntlet_spec(_preset_path(spec.gauntlet_name), spec)
                _print_summary({"status": "saved", "gauntlet_name": spec.gauntlet_name})
            elif action == "2":
                source = input("source [library/custom]: ").strip().lower() or "library"
                if source == "custom":
                    name = input("preset name: ").strip()
                    spec = load_gauntlet_spec(_preset_path(name))
                else:
                    name = input("library preset name: ").strip()
                    spec = _load_library_preset(name)
                _print_summary({"status": "loaded", "gauntlet_name": spec.gauntlet_name})
            elif action == "3":
                if spec is None:
                    raise ValueError("No gauntlet loaded. Choose New or Load first.")
                run_id, config_path = _build_runtime_config(spec)
                cmd = build_launch_command(spec, config_path)
                _print_summary({"run_id": run_id, "gauntlet_name": spec.gauntlet_name, "config_path": config_path, "preview_command": cmd})
            elif action == "4":
                if spec is None:
                    raise ValueError("No gauntlet loaded. Choose New or Load first.")
                run_id, config_path = _build_runtime_config(spec)
                payload = _run_command(build_launch_command(spec, config_path))
                _print_summary({
                    "run_id": payload.get("run_id", run_id),
                    "gauntlet_name": spec.gauntlet_name,
                    "config_path": config_path,
                    "artifacts": payload.get("artifacts"),
                    "verification_pass": payload.get("verification_pass"),
                    "verification_reason": payload.get("verification_reason"),
                    "exit_code": payload.get("exit_code", 1),
                })
            elif action == "5":
                if spec is None:
                    raise ValueError("No gauntlet loaded. Choose New or Load first.")
                run_id, config_path = _build_runtime_config(spec)
                queue.append(
                    QueueItem(
                        gauntlet_name=spec.gauntlet_name,
                        config_path=config_path,
                        command=tuple(build_launch_command(spec, config_path)),
                    )
                )
                _print_summary({"status": "enqueued", "queue_size": len(queue), "run_id": run_id})
            elif action == "6":
                if not queue:
                    raise ValueError("Queue is empty")
                stop_on_fail = _prompt_bool("stop_on_fail")
                queue_id = f"queue-{uuid.uuid4().hex[:10]}"
                manifest_path = write_queue_manifest(
                    QUEUE_DIR / f"{queue_id}.json",
                    queue_id=queue_id,
                    stop_on_fail=stop_on_fail,
                    items=queue,
                )
                receipt_path = process_queue(
                    queue_items=queue,
                    stop_on_fail=stop_on_fail,
                    run_item=_queue_run_item,
                    receipt_path=QUEUE_DIR / f"{queue_id}_receipt.json",
                    queue_id=queue_id,
                )
                queue.clear()
                _print_summary({"queue_id": queue_id, "manifest_path": manifest_path, "receipt_path": receipt_path})
            elif action == "7":
                _print_summary({"recent_artifacts": _show_recent_artifacts()})
            elif action == "8":
                _print_summary(_generate_turn_packet())
            elif action == "9":
                _print_summary({"status": "exit"})
                return 0
            else:
                raise ValueError(f"Unknown menu option: {action}")
        except Exception as exc:
            _print_summary({"status": "error", "error": str(exc)})


if __name__ == "__main__":
    raise SystemExit(main())

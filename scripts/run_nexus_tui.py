#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llama_nexus_lab import control_plane
from llama_nexus_lab.gauntlet import GauntletSpec, QueueItem, load_gauntlet_spec, save_gauntlet_spec

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

SCREENS = ["Dashboard", "Presets", "Queue", "Artifacts", "Turn Packets"]


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


def _parse_source(source_raw: str) -> str:
    source = source_raw.strip().lower()
    if source not in {"library", "custom"}:
        raise ValueError("Invalid source. Expected one of: library, custom")
    return source


# wrappers used by tests

def _available_library_presets() -> list[str]:
    return control_plane.available_library_presets(PRESET_DIR)


def _library_preset_info() -> list[dict[str, str | None]]:
    return control_plane.list_library_presets(PRESET_DIR)


def _resolve_library_selection(selection_raw: str, presets: list[dict[str, str | None]]) -> str:
    return control_plane.resolve_library_selection(selection_raw, presets)


def _load_library_preset(name: str) -> tuple[GauntletSpec, dict[str, str | None]]:
    preset_path = PRESET_DIR / f"{name}.json"
    if not preset_path.exists():
        return control_plane.load_library_preset(name, topic=None, preset_dir=PRESET_DIR)
    payload = json.loads(preset_path.read_text(encoding="utf-8"))
    topic = None
    if "query" not in payload:
        topic = input("topic placeholder value: ").strip() or "default topic"
    return control_plane.load_library_preset(name, topic=topic, preset_dir=PRESET_DIR)


def build_launch_command(spec: GauntletSpec, runtime_config_path: str) -> list[str]:
    return control_plane.build_launch_command(spec, runtime_config_path, repo_root=REPO_ROOT)


def _build_runtime_config(spec: GauntletSpec) -> tuple[str, str]:
    return control_plane.build_runtime_config(spec, base_config=BASE_CONFIG, tui_runs_dir=TUI_RUNS_DIR)


def _persist_run_summary(run_id: str, payload: dict) -> str:
    return control_plane.persist_run_summary(run_id, payload, tui_runs_dir=TUI_RUNS_DIR)


def _persist_queue_summary(queue_id: str, payload: dict) -> str:
    return control_plane.persist_queue_summary(queue_id, payload, queue_dir=QUEUE_DIR)

def _persist_queue_summary(queue_id: str, payload: dict) -> str:
    return control_plane.persist_queue_summary(queue_id, payload, queue_dir=QUEUE_DIR)

def _persist_turn_summary(packet_path: str, payload: dict) -> str:
    return control_plane.persist_turn_summary(packet_path, payload)


def _show_recent_artifacts(limit: int = 5) -> list[dict]:
    return control_plane.list_recent_artifacts(limit=limit, tui_runs_dir=TUI_RUNS_DIR, queue_dir=QUEUE_DIR, email_turns_dir=EMAIL_TURNS_DIR)


def _run_command(cmd: list[str]) -> dict:
    return control_plane.run_command(cmd)


def _build_launch_summary(spec: GauntletSpec, run_id: str, config_path: str, command: list[str], payload: dict) -> dict:
    return control_plane.build_launch_summary(spec, run_id, config_path, command, payload)


def _queue_run_item(item: QueueItem) -> dict:
    return control_plane.queue_run_item(item)


def _generate_turn_packet() -> dict:
    game_id = input("game_id: ").strip() or "default-game"
    turn_raw = input("turn: ").strip()
    if not turn_raw.isdigit() or int(turn_raw) <= 0:
        raise ValueError("turn must be a positive integer")
    move = input("move/action: ").strip()
    actor = input("actor: ").strip() or "operator"
    fen = input("state.fen (optional): ").strip() or "startpos"
    return control_plane.generate_turn_packet(game_id=game_id, turn=int(turn_raw), move=move, actor=actor, fen=fen, email_turns_dir=EMAIL_TURNS_DIR)


def _build_cockpit_snapshot(queue: list[QueueItem]) -> dict:
    return control_plane.build_cockpit_snapshot(
        queue_items=queue,
        preset_dir=PRESET_DIR,
        tui_runs_dir=TUI_RUNS_DIR,
        queue_dir=QUEUE_DIR,
        email_turns_dir=EMAIL_TURNS_DIR,
    )


def _render_menu() -> None:
    print("\nNEXUS Cockpit v2 (fallback mode)")
    for row in MENU:
        print(row)


def _draw_pane(stdscr, y: int, x: int, h: int, w: int, title: str, lines: list[str]) -> None:
    stdscr.addstr(y, x, f"[{title}]"[: max(1, w - 1)])
    for idx, line in enumerate(lines[: max(0, h - 1)]):
        stdscr.addstr(y + idx + 1, x, line[: max(1, w - 1)])


def _screen_main_lines(snapshot: dict, screen: str) -> list[str]:
    if screen == "Dashboard":
        d = snapshot["dashboard"]
        return [f"Queue size: {d['queue_size']}", f"Recent count: {d['recent_count']}", f"Recent kinds: {', '.join([k for k in d['recent_kinds'] if k]) or '(none)'}"]
    if screen == "Presets":
        presets = snapshot["presets"]["presets"][:6]
        return [f"Preset count: {snapshot['presets']['count']}"] + [f"- {p['name']} ({p.get('mode') or 'n/a'})" for p in presets]
    if screen == "Queue":
        queue = snapshot["queue"]
        lines = [f"Queued runs: {queue['queue_size']}"]
        lines += [f"- {item['gauntlet_name']}" for item in queue["items"][:5]]
        return lines
    if screen == "Artifacts":
        artifacts = snapshot["artifacts"]["recent_artifacts"][:5]
        return [f"Recent artifacts: {snapshot['artifacts']['count']}"] + [f"- {row.get('kind')}" for row in artifacts]
    turns = snapshot["turn_packets"]["turn_packets"][:5]
    return [f"Turn packets: {snapshot['turn_packets']['count']}"] + [f"- {row['summary'].get('game_id', 'unknown')}#{row['summary'].get('turn', '?')}" for row in turns]


def _screen_inspector_lines(snapshot: dict, screen: str) -> list[str]:
    if screen == "Dashboard":
        last = snapshot["dashboard"].get("last_recent")
        if not last:
            return ["No recent activity"]
        return ["Latest artifact:", last.get("kind", "unknown"), last.get("path", "")]
    if screen == "Presets":
        first = snapshot["presets"]["presets"][0] if snapshot["presets"]["presets"] else None
        if not first:
            return ["No presets found"]
        return [f"name={first['name']}", f"mode={first.get('mode')}", f"risk={first.get('risk_level')}"]
    if screen == "Queue":
        return ["Queue state is in-memory", f"items={snapshot['queue']['queue_size']}", "Use 5/6 to enqueue/run"]
    if screen == "Artifacts":
        return ["Structured rows from", snapshot["roots"]["tui_runs_dir"], snapshot["roots"]["email_turns_dir"]]
    return ["Turn packet summaries", snapshot["roots"]["email_turns_dir"], "Generated via action 8"]


def _maybe_curses_menu(queue: list[QueueItem]) -> str:
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
            snapshot = _build_cockpit_snapshot(queue)
            screen = SCREENS[current]

            stdscr.clear()
            height, width = stdscr.getmaxyx()
            nav_w = max(18, width // 4)
            detail_w = max(24, width // 4)
            main_w = max(20, width - nav_w - detail_w - 2)

            nav_lines = [f"{'>' if i == current else ' '} {name}" for i, name in enumerate(SCREENS)]
            _draw_pane(stdscr, 0, 0, height - 2, nav_w, "Navigation", nav_lines)
            _draw_pane(stdscr, 0, nav_w + 1, height - 2, main_w, f"Main: {screen}", _screen_main_lines(snapshot, screen))
            _draw_pane(stdscr, 0, nav_w + main_w + 2, height - 2, detail_w, "Inspector", _screen_inspector_lines(snapshot, screen))
            footer = "UP/DOWN screens | 1-9 run action | ENTER default | q exit | state is structured"
            stdscr.addstr(height - 1, 0, footer[: max(1, width - 1)])

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                current = (current - 1) % len(SCREENS)
            elif key in (curses.KEY_DOWN, ord("j")):
                current = (current + 1) % len(SCREENS)
            elif ord("1") <= key <= ord("9"):
                choice["value"] = chr(key)
                break
            elif key in (10, 13):
                defaults = {"Dashboard": "3", "Presets": "2", "Queue": "6", "Artifacts": "7", "Turn Packets": "8"}
                choice["value"] = defaults.get(screen, "9")
                break
            elif key in (ord("q"), 27):
                choice["value"] = "9"
                break
        return 0

    curses.wrapper(_inner)
    return choice["value"]


def _print_summary(summary: dict) -> None:
    print(json.dumps(summary, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NEXUS Cockpit v2")
    parser.add_argument("--dump-state", action="store_true", help="Print machine-readable cockpit state snapshot and exit")
    args = parser.parse_args(argv or [])

    spec: GauntletSpec | None = None
    queue: list[QueueItem] = []

    if args.dump_state:
        _print_summary(_build_cockpit_snapshot(queue))
        return 0

    while True:
        _render_menu()
        action = _maybe_curses_menu(queue)

        try:
            if action == "1":
                spec = _prompt_spec()
                save_gauntlet_spec(_preset_path(spec.gauntlet_name), spec)
                _print_summary({"status": "saved", "gauntlet_name": spec.gauntlet_name})
            elif action == "2":
                source_raw = input("source [library/custom]: ")
                source = _parse_source(source_raw)
                if source == "custom":
                    name = input("preset name: ").strip()
                    spec = load_gauntlet_spec(_preset_path(name))
                    loaded_summary = {"status": "loaded", "gauntlet_name": spec.gauntlet_name}
                else:
                    presets = _library_preset_info()
                    _print_summary({"status": "library_presets", "presets": presets})
                    selection = input("library preset name or index: ").strip()
                    name = _resolve_library_selection(selection, presets)
                    spec, preset_meta = _load_library_preset(name)
                    loaded_summary = {"status": "loaded", "gauntlet_name": spec.gauntlet_name}
                    loaded_summary.update({key: value for key, value in preset_meta.items() if value is not None})
                _print_summary(loaded_summary)
            elif action == "3":
                if spec is None:
                    raise ValueError("No gauntlet loaded. Choose New or Load first.")
                run_id, config_path = _build_runtime_config(spec)
                cmd = build_launch_command(spec, config_path)
                summary = control_plane.build_preview_summary(spec, run_id, config_path, cmd)
                summary["summary_path"] = _persist_run_summary(run_id, summary)
                _print_summary(summary)
            elif action == "4":
                if spec is None:
                    raise ValueError("No gauntlet loaded. Choose New or Load first.")
                run_id, config_path = _build_runtime_config(spec)
                command = build_launch_command(spec, config_path)
                payload = _run_command(command)
                summary = _build_launch_summary(spec, run_id, config_path, command, payload)
                summary["kind"] = "launch"
                summary["status"] = "success" if summary.get("exit_code", 1) == 0 else "fail"
                summary["summary_path"] = _persist_run_summary(run_id, summary)
                _print_summary(summary)
            elif action == "5":
                if spec is None:
                    raise ValueError("No gauntlet loaded. Choose New or Load first.")
                run_id, config_path = _build_runtime_config(spec)
                command = build_launch_command(spec, config_path)
                queue.append(QueueItem(gauntlet_name=spec.gauntlet_name, config_path=config_path, command=tuple(command)))
                summary = {
                    "kind": "enqueue",
                    "status": "enqueued",
                    "queue_size": len(queue),
                    "run_id": run_id,
                    "gauntlet_name": spec.gauntlet_name,
                    "config_path": config_path,
                    "command": command,
                }
                summary["summary_path"] = _persist_run_summary(run_id, summary)
                _print_summary(summary)
            elif action == "6":
                if not queue:
                    raise ValueError("Queue is empty")
                stop_on_fail = _prompt_bool("stop_on_fail")
                queue_id = f"queue-{uuid.uuid4().hex[:10]}"
                summary = control_plane.run_queue(queue, stop_on_fail=stop_on_fail, queue_id=queue_id, queue_dir=QUEUE_DIR, run_item=_queue_run_item)
                queue.clear()
                _print_summary(summary)
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
            error_payload = {"status": "error", "error": str(exc)}
            if "Available presets:" in str(exc):
                _, available_text = str(exc).split("Available presets:", maxsplit=1)
                available = [item.strip() for item in available_text.split(",") if item.strip() and item.strip() != "(none)"]
                error_payload["available_presets"] = available
            _print_summary(error_payload)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

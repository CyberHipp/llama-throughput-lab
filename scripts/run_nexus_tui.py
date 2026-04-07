#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Callable

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


class CockpitState(dict):
    pass


def _new_state() -> CockpitState:
    return CockpitState(
        selected_screen="Dashboard",
        selected_indices={name: 0 for name in SCREENS},
        loaded_spec=None,
        queue=[],
        last_action_result=None,
        last_error=None,
    )


def _prompt_bool(label: str, prompt: Callable[[str], str] | None = None) -> bool:
    prompt = prompt or input
    value = prompt(f"{label} [y/n]: ").strip().lower()
    if value not in {"y", "n"}:
        raise ValueError(f"Invalid boolean input for {label}: '{value}'")
    return value == "y"


def _prompt_spec(prompt: Callable[[str], str] | None = None) -> GauntletSpec:
    prompt = prompt or input
    gauntlet_name = prompt("gauntlet_name: ").strip()
    query = prompt("query: ").strip()
    max_search_intents_raw = prompt("max_search_intents: ").strip()
    if not max_search_intents_raw.isdigit() or int(max_search_intents_raw) <= 0:
        raise ValueError("max_search_intents must be a positive integer")
    spec = GauntletSpec(
        gauntlet_name=gauntlet_name,
        query=query,
        max_search_intents=int(max_search_intents_raw),
        strict_citation_required=_prompt_bool("strict_citation_required", prompt=prompt),
        dry_run=_prompt_bool("dry_run", prompt=prompt),
        require_verify_pass=_prompt_bool("require_verify_pass", prompt=prompt),
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


def _available_library_presets() -> list[str]:
    return control_plane.available_library_presets(PRESET_DIR)


def _library_preset_info() -> list[dict[str, str | None]]:
    return control_plane.list_library_presets(PRESET_DIR)


def _resolve_library_selection(selection_raw: str, presets: list[dict[str, str | None]]) -> str:
    return control_plane.resolve_library_selection(selection_raw, presets)


def _load_library_preset(name: str, prompt: Callable[[str], str] | None = None) -> tuple[GauntletSpec, dict[str, str | None]]:
    prompt = prompt or input
    preset_path = PRESET_DIR / f"{name}.json"
    if not preset_path.exists():
        return control_plane.load_library_preset(name, topic=None, preset_dir=PRESET_DIR)
    payload = json.loads(preset_path.read_text(encoding="utf-8"))
    topic = None
    if "query" not in payload:
        topic = prompt("topic placeholder value: ").strip() or "default topic"
    return control_plane.load_library_preset(name, topic=topic, preset_dir=PRESET_DIR)


def build_launch_command(spec: GauntletSpec, runtime_config_path: str) -> list[str]:
    return control_plane.build_launch_command(spec, runtime_config_path, repo_root=REPO_ROOT)


def _build_runtime_config(spec: GauntletSpec) -> tuple[str, str]:
    return control_plane.build_runtime_config(spec, base_config=BASE_CONFIG, tui_runs_dir=TUI_RUNS_DIR)


def _persist_run_summary(run_id: str, payload: dict) -> str:
    return control_plane.persist_run_summary(run_id, payload, tui_runs_dir=TUI_RUNS_DIR)


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


def _generate_turn_packet(prompt: Callable[[str], str] | None = None) -> dict:
    prompt = prompt or input
    game_id = prompt("game_id: ").strip() or "default-game"
    turn_raw = prompt("turn: ").strip()
    if not turn_raw.isdigit() or int(turn_raw) <= 0:
        raise ValueError("turn must be a positive integer")
    move = prompt("move/action: ").strip()
    actor = prompt("actor: ").strip() or "operator"
    fen = prompt("state.fen (optional): ").strip() or "startpos"
    return control_plane.generate_turn_packet(game_id=game_id, turn=int(turn_raw), move=move, actor=actor, fen=fen, email_turns_dir=EMAIL_TURNS_DIR)


def _build_cockpit_snapshot(state: CockpitState) -> dict:
    return control_plane.build_cockpit_snapshot(
        queue_items=state["queue"],
        preset_dir=PRESET_DIR,
        tui_runs_dir=TUI_RUNS_DIR,
        queue_dir=QUEUE_DIR,
        email_turns_dir=EMAIL_TURNS_DIR,
        loaded_gauntlet=state["loaded_spec"],
        selected_screen=state["selected_screen"],
        selected_indices=state["selected_indices"],
        last_action_result=state["last_action_result"],
        last_error=state["last_error"],
    )


def _screen_item_count(snapshot: dict, screen: str) -> int:
    if screen == "Presets":
        return max(1, snapshot["presets"]["count"])
    if screen == "Queue":
        return max(1, snapshot["queue"]["queue_size"])
    if screen == "Artifacts":
        return max(1, snapshot["artifacts"]["count"])
    if screen == "Turn Packets":
        return max(1, snapshot["turn_packets"]["count"])
    return 1


def _render_menu() -> None:
    print("\nNEXUS Cockpit v2 (fallback mode)")
    for row in MENU:
        print(row)


def _print_summary(summary: dict) -> None:
    print(json.dumps(summary, sort_keys=True))


def _execute_action(action: str, state: CockpitState, prompt: Callable[[str], str]) -> tuple[bool, dict]:
    spec: GauntletSpec | None = state["loaded_spec"]
    queue: list[QueueItem] = state["queue"]

    if action == "1":
        spec = _prompt_spec(prompt=prompt)
        save_gauntlet_spec(_preset_path(spec.gauntlet_name), spec)
        state["loaded_spec"] = spec
        return False, {"status": "saved", "gauntlet_name": spec.gauntlet_name}
    if action == "2":
        source = _parse_source(prompt("source [library/custom]: "))
        if source == "custom":
            name = prompt("preset name: ").strip()
            spec = load_gauntlet_spec(_preset_path(name))
            state["loaded_spec"] = spec
            return False, {"status": "loaded", "gauntlet_name": spec.gauntlet_name}
        presets = _library_preset_info()
        if not presets:
            raise ValueError("No library presets available")
        selected_idx = state["selected_indices"].get("Presets", 0)
        selection_default = str(min(selected_idx + 1, len(presets)))
        selection = prompt(f"library preset name or index [{selection_default}]: ").strip() or selection_default
        name = _resolve_library_selection(selection, presets)
        spec, preset_meta = _load_library_preset(name, prompt=prompt)
        state["loaded_spec"] = spec
        summary = {"status": "loaded", "gauntlet_name": spec.gauntlet_name}
        summary.update({k: v for k, v in preset_meta.items() if v is not None})
        return False, summary
    if action == "3":
        if spec is None:
            raise ValueError("No gauntlet loaded. Choose New or Load first.")
        run_id, config_path = _build_runtime_config(spec)
        cmd = build_launch_command(spec, config_path)
        summary = control_plane.build_preview_summary(spec, run_id, config_path, cmd)
        summary["summary_path"] = _persist_run_summary(run_id, summary)
        return False, summary
    if action == "4":
        if spec is None:
            raise ValueError("No gauntlet loaded. Choose New or Load first.")
        run_id, config_path = _build_runtime_config(spec)
        command = build_launch_command(spec, config_path)
        payload = _run_command(command)
        summary = _build_launch_summary(spec, run_id, config_path, command, payload)
        summary["kind"] = "launch"
        summary["status"] = "success" if summary.get("exit_code", 1) == 0 else "fail"
        summary["summary_path"] = _persist_run_summary(run_id, summary)
        return False, summary
    if action == "5":
        if spec is None:
            raise ValueError("No gauntlet loaded. Choose New or Load first.")
        run_id, config_path = _build_runtime_config(spec)
        command = build_launch_command(spec, config_path)
        queue.append(QueueItem(gauntlet_name=spec.gauntlet_name, config_path=config_path, command=tuple(command)))
        summary = {"kind": "enqueue", "status": "enqueued", "queue_size": len(queue), "run_id": run_id, "gauntlet_name": spec.gauntlet_name, "config_path": config_path, "command": command}
        summary["summary_path"] = _persist_run_summary(run_id, summary)
        return False, summary
    if action == "6":
        if not queue:
            raise ValueError("Queue is empty")
        stop_on_fail = _prompt_bool("stop_on_fail", prompt=prompt)
        queue_id = f"queue-{uuid.uuid4().hex[:10]}"
        summary = control_plane.run_queue(queue, stop_on_fail=stop_on_fail, queue_id=queue_id, queue_dir=QUEUE_DIR, run_item=_queue_run_item)
        queue.clear()
        return False, summary
    if action == "7":
        return False, {"recent_artifacts": _show_recent_artifacts()}
    if action == "8":
        return False, _generate_turn_packet(prompt=prompt)
    if action == "9":
        return True, {"status": "exit"}
    raise ValueError(f"Unknown menu option: {action}")


def _curses_prompt_factory(stdscr):
    import curses

    def _prompt(label: str) -> str:
        height, width = stdscr.getmaxyx()
        prompt = label[: max(1, width - 1)]
        stdscr.addstr(height - 1, 0, " " * (width - 1))
        stdscr.addstr(height - 1, 0, prompt)
        stdscr.clrtoeol()
        stdscr.refresh()
        curses.echo()
        raw = stdscr.getstr(height - 1, min(len(prompt), width - 2), max(1, width - len(prompt) - 2))
        curses.noecho()
        return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

    return _prompt


def _screen_main_lines(snapshot: dict, screen: str) -> list[str]:
    if screen == "Dashboard":
        loaded = snapshot["cockpit"].get("loaded_gauntlet")
        d = snapshot["dashboard"]
        return [
            f"Loaded: {(loaded or {}).get('gauntlet_name', '(none)')}",
            f"Queue size: {d['queue_size']}",
            f"Recent artifacts: {d['recent_count']}",
            f"Last action: {(snapshot['cockpit'].get('last_action_result') or {}).get('status', '(none)')}",
        ]
    if screen == "Presets":
        rows = snapshot["presets"]["presets"][:6]
        return [f"Preset count: {snapshot['presets']['count']}"] + [f"- {r['name']} ({r.get('mode') or 'n/a'})" for r in rows]
    if screen == "Queue":
        rows = snapshot["queue"]["items"][:6]
        return [f"Queued items: {snapshot['queue']['queue_size']}"] + [f"- {r['gauntlet_name']}" for r in rows]
    if screen == "Artifacts":
        rows = snapshot["artifacts"]["recent_artifacts"][:6]
        return [f"Artifact rows: {snapshot['artifacts']['count']}"] + [f"- {r.get('kind')}" for r in rows]
    rows = snapshot["turn_packets"]["turn_packets"][:6]
    return [f"Turn packets: {snapshot['turn_packets']['count']}"] + [f"- {r['summary'].get('game_id', 'unknown')}#{r['summary'].get('turn', '?')}" for r in rows]


def _screen_inspector_lines(snapshot: dict, screen: str) -> list[str]:
    idx = snapshot["cockpit"]["selected_indices"].get(screen, 0)
    if screen == "Presets" and snapshot["presets"]["presets"]:
        row = snapshot["presets"]["presets"][min(idx, len(snapshot["presets"]["presets"]) - 1)]
        return [f"name={row['name']}", f"mode={row.get('mode')}", f"risk={row.get('risk_level')}", f"notes={row.get('notes')}"]
    if screen == "Queue" and snapshot["queue"]["items"]:
        row = snapshot["queue"]["items"][min(idx, len(snapshot["queue"]["items"]) - 1)]
        return [f"gauntlet={row['gauntlet_name']}", f"config={row['config_path']}", f"cmd={' '.join(row['command'][:3])}..."]
    if screen == "Artifacts" and snapshot["artifacts"]["recent_artifacts"]:
        row = snapshot["artifacts"]["recent_artifacts"][min(idx, len(snapshot["artifacts"]["recent_artifacts"]) - 1)]
        return [f"kind={row.get('kind')}", f"path={row.get('path', '')}"]
    if screen == "Turn Packets" and snapshot["turn_packets"]["turn_packets"]:
        row = snapshot["turn_packets"]["turn_packets"][min(idx, len(snapshot["turn_packets"]["turn_packets"]) - 1)]
        s = row["summary"]
        return [f"game_id={s.get('game_id')}", f"turn={s.get('turn')}", f"packet={s.get('packet_path')}"]
    err = snapshot["cockpit"].get("last_error")
    if err:
        return ["last_error", err]
    return ["No item selected"]


def _run_fullscreen_cockpit(state: CockpitState) -> dict:
    import curses

    result: dict = {"status": "exit"}

    def _inner(stdscr):
        nonlocal result
        curses.curs_set(0)
        while True:
            snapshot = _build_cockpit_snapshot(state)
            screen = state["selected_screen"]

            stdscr.clear()
            h, w = stdscr.getmaxyx()
            nav_w = max(18, w // 4)
            detail_w = max(28, w // 3)
            main_w = max(20, w - nav_w - detail_w - 2)

            nav_lines = [f"{'>' if s == screen else ' '} {s}" for s in SCREENS]
            _draw = lambda y, x, hh, ww, title, lines: (
                stdscr.addstr(y, x, f"[{title}]"[: max(1, ww - 1)]),
                [stdscr.addstr(y + i + 1, x, line[: max(1, ww - 1)]) for i, line in enumerate(lines[: max(0, hh - 1)])],
            )
            _draw(0, 0, h - 2, nav_w, "Navigation", nav_lines)
            _draw(0, nav_w + 1, h - 2, main_w, f"Main: {screen}", _screen_main_lines(snapshot, screen))
            _draw(0, nav_w + main_w + 2, h - 2, detail_w, "Inspector", _screen_inspector_lines(snapshot, screen))
            footer = "UP/DOWN screens | LEFT/RIGHT select | 1-9 actions | q exit"
            stdscr.addstr(h - 1, 0, footer[: max(1, w - 1)])
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                idx = (SCREENS.index(screen) - 1) % len(SCREENS)
                state["selected_screen"] = SCREENS[idx]
            elif key in (curses.KEY_DOWN, ord("j")):
                idx = (SCREENS.index(screen) + 1) % len(SCREENS)
                state["selected_screen"] = SCREENS[idx]
            elif key in (curses.KEY_LEFT, ord("h"), curses.KEY_RIGHT, ord("l")):
                delta = -1 if key in (curses.KEY_LEFT, ord("h")) else 1
                total = _screen_item_count(snapshot, screen)
                current = state["selected_indices"].get(screen, 0)
                state["selected_indices"][screen] = max(0, min(total - 1, current + delta))
            elif ord("1") <= key <= ord("9"):
                action = chr(key)
                try:
                    should_exit, result = _execute_action(action, state, prompt=_curses_prompt_factory(stdscr))
                    state["last_action_result"] = result
                    state["last_error"] = None
                    if should_exit:
                        break
                except Exception as exc:
                    state["last_error"] = str(exc)
            elif key in (ord("q"), 27):
                result = {"status": "exit"}
                break

    curses.wrapper(_inner)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NEXUS Cockpit v2")
    parser.add_argument("--dump-state", action="store_true", help="Print machine-readable cockpit state snapshot and exit")
    args = parser.parse_args(argv or [])

    state = _new_state()

    if args.dump_state:
        _print_summary(_build_cockpit_snapshot(state))
        return 0

    if sys.stdin.isatty() and os.environ.get("TERM") not in {None, "dumb"}:
        try:
            _print_summary(_run_fullscreen_cockpit(state))
            return 0
        except Exception:
            pass

    while True:
        _render_menu()
        action = input("Choose menu option [1-9]: ").strip()
        try:
            should_exit, result = _execute_action(action, state, prompt=input)
            state["last_action_result"] = result
            state["last_error"] = None
            _print_summary(result)
            if should_exit:
                return 0
        except Exception as exc:
            state["last_error"] = str(exc)
            error_payload = {"status": "error", "error": str(exc)}
            if "Available presets:" in str(exc):
                _, available_text = str(exc).split("Available presets:", maxsplit=1)
                available = [item.strip() for item in available_text.split(",") if item.strip() and item.strip() != "(none)"]
                error_payload["available_presets"] = available
            _print_summary(error_payload)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

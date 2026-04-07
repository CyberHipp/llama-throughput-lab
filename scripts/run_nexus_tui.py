#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
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
SESSION_PATH = REPO_ROOT / "artifacts/nexus/cockpit_state/session.json"
RECEIPTS_DIR = REPO_ROOT / "artifacts/nexus/cockpit_state/receipts"

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
ACTION_MAP = {
    "new_gauntlet": "1",
    "load_preset": "2",
    "preview": "3",
    "launch": "4",
    "enqueue": "5",
    "run_queue": "6",
    "show_recent_artifacts": "7",
    "generate_turn_packet": "8",
    "exit": "9",
    "reset_queue": "reset_queue",
    "clear_last_error": "clear_last_error",
}


class CockpitState(dict):
    pass


def _new_state() -> CockpitState:
    session = control_plane.load_cockpit_session_state(SESSION_PATH)
    queue_items = [QueueItem(gauntlet_name=i["gauntlet_name"], config_path=i["config_path"], command=tuple(i["command"])) for i in session.get("queue_items", [])]
    return CockpitState(
        selected_screen=session.get("selected_screen", "Dashboard"),
        selected_indices=session.get("selected_indices", {name: 0 for name in SCREENS}),
        loaded_spec=control_plane.dict_to_spec(session.get("loaded_gauntlet")),
        queue=queue_items,
        last_action_result=session.get("last_action_result"),
        last_error=session.get("last_error"),
        last_action_receipt_path=session.get("last_action_receipt_path"),
    )


def _save_state(state: CockpitState) -> str:
    payload = {
        "selected_screen": state["selected_screen"],
        "selected_indices": state["selected_indices"],
        "loaded_gauntlet": control_plane.spec_to_dict(state.get("loaded_spec")),
        "queue_items": [{"gauntlet_name": q.gauntlet_name, "config_path": q.config_path, "command": list(q.command)} for q in state["queue"]],
        "last_action_result": state.get("last_action_result"),
        "last_error": state.get("last_error"),
        "last_action_receipt_path": state.get("last_action_receipt_path"),
    }
    return control_plane.save_cockpit_session_state(payload, state_path=SESSION_PATH)


def _prompt_bool(label: str, prompt: Callable[[str], str] | None = None) -> bool:
    prompt = prompt or input
    value = prompt(f"{label} [y/n]: ").strip().lower()
    if value not in {"y", "n"}:
        raise ValueError(f"Invalid boolean input for {label}: '{value}'")
    return value == "y"


def _prompt_spec(prompt: Callable[[str], str] | None = None) -> GauntletSpec:
    prompt = prompt or input
    spec = GauntletSpec(
        gauntlet_name=prompt("gauntlet_name: ").strip(),
        query=prompt("query: ").strip(),
        max_search_intents=int(prompt("max_search_intents: ").strip()),
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
    topic = prompt("topic placeholder value: ").strip() if "query" not in payload else None
    return control_plane.load_library_preset(name, topic=topic or None, preset_dir=PRESET_DIR)


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
    return control_plane.generate_turn_packet(
        game_id=game_id,
        turn=int(turn_raw),
        move=prompt("move/action: ").strip(),
        actor=prompt("actor: ").strip() or "operator",
        fen=prompt("state.fen (optional): ").strip() or "startpos",
        email_turns_dir=EMAIL_TURNS_DIR,
    )


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
        session_state_path=str(SESSION_PATH),
        last_action_receipt_path=state.get("last_action_receipt_path"),
    )


def _screen_item_count(snapshot: dict, screen: str) -> int:
    mapping = {
        "Presets": snapshot["presets"]["count"],
        "Queue": snapshot["queue"]["queue_size"],
        "Artifacts": snapshot["artifacts"]["count"],
        "Turn Packets": snapshot["turn_packets"]["count"],
    }
    return max(1, mapping.get(screen, 1))


def _perform_action(action: str, state: CockpitState, values: dict) -> tuple[bool, dict]:
    spec: GauntletSpec | None = state["loaded_spec"]
    queue: list[QueueItem] = state["queue"]

    if action == "1":
        state["loaded_spec"] = values["spec"]
        save_gauntlet_spec(_preset_path(values["spec"].gauntlet_name), values["spec"])
        return False, {"status": "saved", "gauntlet_name": values["spec"].gauntlet_name}
    if action == "2":
        if values["source"] == "custom":
            state["loaded_spec"] = load_gauntlet_spec(_preset_path(values["name"]))
            return False, {"status": "loaded", "gauntlet_name": state["loaded_spec"].gauntlet_name}
        loaded_spec, preset_meta = _load_library_preset(values["name"], prompt=values.get("prompt"))
        state["loaded_spec"] = loaded_spec
        out = {"status": "loaded", "gauntlet_name": loaded_spec.gauntlet_name}
        out.update({k: v for k, v in preset_meta.items() if v is not None})
        return False, out
    if action == "3":
        if spec is None:
            raise ValueError("No gauntlet loaded. Choose New or Load first.")
        run_id, config_path = _build_runtime_config(spec)
        cmd = build_launch_command(spec, config_path)
        out = control_plane.build_preview_summary(spec, run_id, config_path, cmd)
        out["summary_path"] = _persist_run_summary(run_id, out)
        return False, out
    if action == "4":
        if spec is None:
            raise ValueError("No gauntlet loaded. Choose New or Load first.")
        run_id, config_path = _build_runtime_config(spec)
        command = build_launch_command(spec, config_path)
        payload = _run_command(command)
        out = _build_launch_summary(spec, run_id, config_path, command, payload)
        out["kind"] = "launch"
        out["status"] = "success" if out.get("exit_code", 1) == 0 else "fail"
        out["summary_path"] = _persist_run_summary(run_id, out)
        return False, out
    if action == "5":
        if spec is None:
            raise ValueError("No gauntlet loaded. Choose New or Load first.")
        run_id, config_path = _build_runtime_config(spec)
        command = build_launch_command(spec, config_path)
        queue.append(QueueItem(gauntlet_name=spec.gauntlet_name, config_path=config_path, command=tuple(command)))
        out = {"kind": "enqueue", "status": "enqueued", "queue_size": len(queue), "run_id": run_id, "gauntlet_name": spec.gauntlet_name, "config_path": config_path, "command": command}
        out["summary_path"] = _persist_run_summary(run_id, out)
        return False, out
    if action == "6":
        if not queue:
            raise ValueError("Queue is empty")
        stop_on_fail = bool(values.get("stop_on_fail", False))
        queue_id = f"queue-{uuid.uuid4().hex[:10]}"
        out = control_plane.run_queue(queue, stop_on_fail=stop_on_fail, queue_id=queue_id, queue_dir=QUEUE_DIR, run_item=_queue_run_item)
        queue.clear()
        return False, out
    if action == "7":
        return False, {"recent_artifacts": _show_recent_artifacts()}
    if action == "8":
        return False, _generate_turn_packet(prompt=values.get("prompt"))
    if action == "reset_queue":
        queue.clear()
        return False, {"status": "queue_reset", "queue_size": 0}
    if action == "clear_last_error":
        state["last_error"] = None
        return False, {"status": "last_error_cleared"}
    if action == "9":
        return True, {"status": "exit"}
    raise ValueError(f"Unknown menu option: {action}")


def _execute_action(action: str, state: CockpitState, prompt: Callable[[str], str]) -> tuple[bool, dict]:
    if action == "1":
        return _perform_action(action, state, {"spec": _prompt_spec(prompt=prompt)})
    if action == "2":
        source = _parse_source(prompt("source [library/custom]: "))
        if source == "custom":
            return _perform_action(action, state, {"source": source, "name": prompt("preset name: ").strip()})
        presets = _library_preset_info()
        if not presets:
            raise ValueError("No library presets available")
        default_idx = str(min(state["selected_indices"].get("Presets", 0) + 1, len(presets)))
        selection = prompt(f"library preset name or index [{default_idx}]: ").strip() or default_idx
        return _perform_action(action, state, {"source": source, "name": _resolve_library_selection(selection, presets), "prompt": prompt})
    if action == "6":
        return _perform_action(action, state, {"stop_on_fail": _prompt_bool("stop_on_fail", prompt=prompt)})
    if action == "8":
        return _perform_action(action, state, {"prompt": prompt})
    return _perform_action(action, state, {})


def _execute_bridge_action(payload: dict, state: CockpitState) -> dict:
    action_name = payload.get("action")
    action = ACTION_MAP.get(action_name)
    if not action:
        raise ValueError(f"Unsupported action: {action_name}")
    if action in {"reset_queue", "clear_last_error"}:
        _, result = _perform_action(action, state, {})
        return result

    if action == "1":
        spec = GauntletSpec(**payload["spec"])
        spec.validate()
        _, result = _perform_action("1", state, {"spec": spec})
        return result
    if action == "2":
        source = _parse_source(payload.get("source", "library"))
        name = payload.get("name") or payload.get("selection")
        if source == "library" and name is None:
            raise ValueError("load_preset requires 'name' or 'selection'")
        if source == "library" and str(name).isdigit():
            name = _resolve_library_selection(str(name), _library_preset_info())
        prompt = lambda _label: str(payload.get("topic", "default topic"))
        _, result = _perform_action("2", state, {"source": source, "name": str(name), "prompt": prompt})
        return result
    if action == "6":
        _, result = _perform_action("6", state, {"stop_on_fail": bool(payload.get("stop_on_fail", False))})
        return result
    if action == "8":
        fields = {
            "game_id": payload.get("game_id", "default-game"),
            "turn": str(payload.get("turn", 1)),
            "move/action": payload.get("move", ""),
            "actor": payload.get("actor", "operator"),
            "state.fen (optional)": payload.get("fen", "startpos"),
        }
        prompt = lambda label: str(fields.get(label.rstrip(": "), fields.get(label, "")))
        _, result = _perform_action("8", state, {"prompt": prompt})
        return result

    _, result = _perform_action(action, state, {})
    return result


def _write_action_receipt(action: str, status: str, state: CockpitState, result: dict | None = None, error: str | None = None, error_type: str | None = None) -> str:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + f"-{uuid.uuid4().hex[:8]}"
    path = RECEIPTS_DIR / f"{receipt_id}.json"
    snapshot = _build_cockpit_snapshot(state)
    payload = {
        "receipt_version": control_plane.RECEIPT_VERSION,
        "action_result_version": control_plane.ACTION_RESULT_VERSION,
        "action": action,
        "status": status,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "session_state_path": str(SESSION_PATH),
        "result": result,
        "error": error,
        "error_type": error_type,
        "snapshot": snapshot,
    }
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    state["last_action_receipt_path"] = str(path)
    return str(path)


def _render_menu() -> None:
    print("\nNEXUS Cockpit v2 (fallback mode)")
    for row in MENU:
        print(row)


def _print_summary(summary: dict) -> None:
    print(json.dumps(summary, sort_keys=True))


def _curses_prompt_factory(stdscr):
    import curses

    def _prompt(label: str) -> str:
        h, w = stdscr.getmaxyx()
        stdscr.addstr(h - 1, 0, " " * (w - 1))
        prompt = label[: max(1, w - 1)]
        stdscr.addstr(h - 1, 0, prompt)
        stdscr.refresh()
        curses.echo()
        raw = stdscr.getstr(h - 1, min(len(prompt), w - 2), max(1, w - len(prompt) - 2))
        curses.noecho()
        return raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)

    return _prompt


def _screen_main_lines(snapshot: dict, screen: str) -> list[str]:
    if screen == "Dashboard":
        loaded = snapshot["cockpit"].get("loaded_gauntlet") or {}
        return [f"Loaded: {loaded.get('gauntlet_name', '(none)')}", f"Queue size: {snapshot['queue']['queue_size']}", f"Recent artifacts: {snapshot['artifacts']['count']}", f"Last status: {(snapshot['cockpit'].get('last_action_result') or {}).get('status', '(none)')}" ]
    if screen == "Presets":
        return [f"Preset count: {snapshot['presets']['count']}"] + [f"- {p['name']}" for p in snapshot["presets"]["presets"][:6]]
    if screen == "Queue":
        return [f"Queue items: {snapshot['queue']['queue_size']}"] + [f"- {q['gauntlet_name']}" for q in snapshot["queue"]["items"][:6]]
    if screen == "Artifacts":
        return [f"Recent artifacts: {snapshot['artifacts']['count']}"] + [f"- {a.get('kind')}" for a in snapshot["artifacts"]["recent_artifacts"][:6]]
    return [f"Turn packets: {snapshot['turn_packets']['count']}"] + [f"- {r['summary'].get('game_id')}#{r['summary'].get('turn')}" for r in snapshot["turn_packets"]["turn_packets"][:6]]


def _screen_inspector_lines(snapshot: dict, screen: str) -> list[str]:
    idx = snapshot["cockpit"]["selected_indices"].get(screen, 0)
    if screen == "Presets" and snapshot["presets"]["presets"]:
        p = snapshot["presets"]["presets"][min(idx, len(snapshot["presets"]["presets"]) - 1)]
        return [f"name={p['name']}", f"mode={p.get('mode')}", f"risk={p.get('risk_level')}"]
    if screen == "Queue" and snapshot["queue"]["items"]:
        q = snapshot["queue"]["items"][min(idx, len(snapshot["queue"]["items"]) - 1)]
        return [f"gauntlet={q['gauntlet_name']}", f"config={q['config_path']}"]
    if screen == "Artifacts" and snapshot["artifacts"]["recent_artifacts"]:
        a = snapshot["artifacts"]["recent_artifacts"][min(idx, len(snapshot["artifacts"]["recent_artifacts"]) - 1)]
        return [f"kind={a.get('kind')}", f"path={a.get('path', '')}"]
    if screen == "Turn Packets" and snapshot["turn_packets"]["turn_packets"]:
        t = snapshot["turn_packets"]["turn_packets"][min(idx, len(snapshot["turn_packets"]["turn_packets"]) - 1)]["summary"]
        return [f"game_id={t.get('game_id')}", f"turn={t.get('turn')}", f"packet={t.get('packet_path')}"]
    return [snapshot["cockpit"].get("last_error") or "No item selected"]


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
            nav_w, detail_w = max(18, w // 4), max(26, w // 3)
            main_w = max(20, w - nav_w - detail_w - 2)

            def draw(y, x, hh, ww, title, lines):
                stdscr.addstr(y, x, f"[{title}]"[: max(1, ww - 1)])
                for i, line in enumerate(lines[: max(0, hh - 1)]):
                    stdscr.addstr(y + i + 1, x, line[: max(1, ww - 1)])

            draw(0, 0, h - 2, nav_w, "Navigation", [f"{'>' if s == screen else ' '} {s}" for s in SCREENS])
            draw(0, nav_w + 1, h - 2, main_w, f"Main: {screen}", _screen_main_lines(snapshot, screen))
            draw(0, nav_w + main_w + 2, h - 2, detail_w, "Inspector", _screen_inspector_lines(snapshot, screen))
            stdscr.addstr(h - 1, 0, "UP/DOWN screens | LEFT/RIGHT select | 1-9 actions | q exit"[: max(1, w - 1)])
            stdscr.refresh()

            key = stdscr.getch()
            if key in (curses.KEY_UP, ord("k")):
                state["selected_screen"] = SCREENS[(SCREENS.index(screen) - 1) % len(SCREENS)]
            elif key in (curses.KEY_DOWN, ord("j")):
                state["selected_screen"] = SCREENS[(SCREENS.index(screen) + 1) % len(SCREENS)]
            elif key in (curses.KEY_LEFT, ord("h"), curses.KEY_RIGHT, ord("l")):
                delta = -1 if key in (curses.KEY_LEFT, ord("h")) else 1
                total = _screen_item_count(snapshot, screen)
                state["selected_indices"][screen] = max(0, min(total - 1, state["selected_indices"].get(screen, 0) + delta))
            elif ord("1") <= key <= ord("9"):
                try:
                    should_exit, result = _execute_action(chr(key), state, prompt=_curses_prompt_factory(stdscr))
                    state["last_action_result"] = result
                    state["last_error"] = None
                    _write_action_receipt(action=chr(key), status="ok", state=state, result=result)
                    _save_state(state)
                    if should_exit:
                        break
                except Exception as exc:
                    state["last_error"] = str(exc)
                    _write_action_receipt(action=chr(key), status="error", state=state, error=str(exc), error_type=type(exc).__name__)
                    _save_state(state)
            elif key in (ord("q"), 27):
                result = {"status": "exit"}
                break

    curses.wrapper(_inner)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NEXUS Cockpit v2")
    parser.add_argument("--dump-state", action="store_true", help="Print machine-readable cockpit state snapshot and exit")
    parser.add_argument("--action-json", help="Run one machine-readable cockpit action payload")
    parser.add_argument("--action-file", help="Path to JSON payload for one machine-readable cockpit action")
    args = parser.parse_args(argv or [])

    state = _new_state()

    if args.dump_state:
        _print_summary(_build_cockpit_snapshot(state))
        return 0

    if args.action_json or args.action_file:
        try:
            payload = json.loads(args.action_json) if args.action_json else json.loads(Path(args.action_file).read_text(encoding="utf-8"))
            result = _execute_bridge_action(payload, state)
            state["last_action_result"] = result
            state["last_error"] = None
            _write_action_receipt(action=str(payload.get("action", "unknown")), status="ok", state=state, result=result)
            _save_state(state)
            _print_summary({"status": "ok", "action_result_version": control_plane.ACTION_RESULT_VERSION, "result": result, "snapshot": _build_cockpit_snapshot(state), "receipt_path": state.get("last_action_receipt_path") })
            return 0
        except Exception as exc:
            state["last_error"] = str(exc)
            _write_action_receipt(action=str(payload.get("action", "unknown") if "payload" in locals() else "unknown"), status="error", state=state, error=str(exc), error_type=type(exc).__name__)
            _save_state(state)
            _print_summary({"status": "error", "action_result_version": control_plane.ACTION_RESULT_VERSION, "error_type": type(exc).__name__, "error": str(exc), "snapshot": _build_cockpit_snapshot(state), "receipt_path": state.get("last_action_receipt_path") })
            return 1

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
            _write_action_receipt(action=action, status="ok", state=state, result=result)
            _save_state(state)
            _print_summary(result)
            if should_exit:
                return 0
        except Exception as exc:
            state["last_error"] = str(exc)
            _write_action_receipt(action=action, status="error", state=state, error=str(exc), error_type=type(exc).__name__)
            _save_state(state)
            err = {"status": "error", "error": str(exc)}
            if "Available presets:" in str(exc):
                _, available_text = str(exc).split("Available presets:", maxsplit=1)
                err["available_presets"] = [i.strip() for i in available_text.split(",") if i.strip() and i.strip() != "(none)"]
            _print_summary(err)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

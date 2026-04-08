from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

from llama_nexus_lab.email_turn_adapter import build_email_bundle, build_turn_packet, serialize_turn_packet
from llama_nexus_lab.gauntlet import GauntletSpec, QueueItem, build_temp_runtime_config, process_queue, write_queue_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = REPO_ROOT / "configs/nexus/default.json"
PRESET_DIR = REPO_ROOT / "configs/nexus/gauntlets/presets"
TUI_RUNS_DIR = REPO_ROOT / "artifacts/nexus/tui_runs"
QUEUE_DIR = TUI_RUNS_DIR / "queue"
EMAIL_TURNS_DIR = REPO_ROOT / "artifacts/nexus/email_turns"
COCKPIT_STATE_PATH = REPO_ROOT / "artifacts/nexus/cockpit_state/session.json"
COCKPIT_SCREENS = ["Dashboard", "Presets", "Queue", "Artifacts", "Turn Packets"]
SNAPSHOT_VERSION = "nexus-cockpit-snapshot-v1"
ACTION_RESULT_VERSION = "nexus-cockpit-action-result-v1"
RECEIPT_VERSION = "nexus-cockpit-action-receipt-v1"


def available_library_presets(preset_dir: Path = PRESET_DIR) -> list[str]:
    if not preset_dir.exists():
        return []
    return sorted(path.stem for path in preset_dir.glob("*.json"))


def list_library_presets(preset_dir: Path = PRESET_DIR) -> list[dict[str, str | None]]:
    entries: list[dict[str, str | None]] = []
    for name in available_library_presets(preset_dir):
        payload = json.loads((preset_dir / f"{name}.json").read_text(encoding="utf-8"))
        entries.append(
            {
                "name": name,
                "mode": payload.get("mode"),
                "risk_level": payload.get("risk_level"),
                "notes": payload.get("notes"),
            }
        )
    return entries


def resolve_library_selection(selection_raw: str, presets: list[dict[str, str | None]]) -> str:
    selection = selection_raw.strip()
    names = [str(row["name"]) for row in presets]
    if selection.isdigit():
        index = int(selection)
        if index < 1 or index > len(names):
            raise ValueError(f"Library selection '{selection}' is out of range. Available presets: {', '.join(names)}")
        return names[index - 1]
    if selection in names:
        return selection
    raise FileNotFoundError(f"Library preset '{selection}' not found. Available presets: {', '.join(names)}")


def load_library_preset(name: str, topic: str | None = None, preset_dir: Path = PRESET_DIR) -> tuple[GauntletSpec, dict[str, str | None]]:
    preset_path = preset_dir / f"{name}.json"
    if not preset_path.exists():
        available = available_library_presets(preset_dir)
        raise FileNotFoundError(
            f"Library preset '{name}' not found. Available presets: {', '.join(available) if available else '(none)'}"
        )

    payload = json.loads(preset_path.read_text(encoding="utf-8"))
    if "query" not in payload:
        template = payload.get("query_template", "")
        payload["query"] = template.replace("{topic}", topic or "default topic")

    spec = GauntletSpec(
        gauntlet_name=payload["gauntlet_name"],
        query=payload["query"],
        max_search_intents=int(payload["max_search_intents"]),
        strict_citation_required=bool(payload["strict_citation_required"]),
        dry_run=bool(payload["dry_run"]),
        require_verify_pass=bool(payload["require_verify_pass"]),
    )
    spec.validate()
    return spec, {
        "mode": payload.get("mode"),
        "risk_level": payload.get("risk_level"),
        "notes": payload.get("notes"),
    }


def build_launch_command(spec: GauntletSpec, runtime_config_path: str, repo_root: Path = REPO_ROOT) -> list[str]:
    governed_path = repo_root / "scripts/run_nexus_governed_smoke.py"
    pipeline_path = repo_root / "scripts/run_nexus_pipeline.py"

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


def build_runtime_config(spec: GauntletSpec, base_config: Path = BASE_CONFIG, tui_runs_dir: Path = TUI_RUNS_DIR) -> tuple[str, str]:
    run_id = f"tui-{uuid.uuid4().hex[:10]}"
    run_dir = tui_runs_dir / run_id
    config_path = run_dir / "config.json"
    build_temp_runtime_config(base_config, spec, config_path)
    return run_id, str(config_path)


def write_summary(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return str(path)


def persist_run_summary(run_id: str, payload: dict, tui_runs_dir: Path = TUI_RUNS_DIR) -> str:
    return write_summary(tui_runs_dir / run_id / "tui_summary.json", payload)


def persist_queue_summary(queue_id: str, payload: dict, queue_dir: Path = QUEUE_DIR) -> str:
    return write_summary(queue_dir / f"{queue_id}_summary.json", payload)


def persist_turn_summary(packet_path: str, payload: dict) -> str:
    packet_file = Path(packet_path)
    summary_path = packet_file.with_name(f"{packet_file.stem}_summary.json")
    return write_summary(summary_path, payload)


def run_command(cmd: list[str]) -> dict:
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


def build_preview_summary(spec: GauntletSpec, run_id: str, config_path: str, command: list[str]) -> dict:
    return {
        "kind": "preview",
        "status": "preview",
        "run_id": run_id,
        "gauntlet_name": spec.gauntlet_name,
        "config_path": config_path,
        "command": command,
        "preview_command": command,
    }


def build_launch_summary(spec: GauntletSpec, run_id: str, config_path: str, command: list[str], payload: dict) -> dict:
    reason = payload.get("verification_reason") or payload.get("reason")
    if not reason and payload.get("exit_code", 1) != 0:
        reason = payload.get("stderr") or "run failed"
    summary = {
        "run_id": payload.get("run_id", run_id),
        "gauntlet_name": spec.gauntlet_name,
        "config_path": config_path,
        "command": command,
        "artifacts": payload.get("artifacts"),
        "verification_pass": payload.get("verification_pass"),
        "verification_reason": payload.get("verification_reason"),
        "exit_code": payload.get("exit_code", 1),
    }
    if payload.get("stderr"):
        summary["stderr"] = payload["stderr"]
    if reason:
        summary["reason"] = reason
    return summary


def queue_run_item(item: QueueItem) -> dict:
    payload = run_command(list(item.command))
    return {
        "run_id": payload.get("run_id"),
        "exit_code": payload.get("exit_code", 1),
        "reason": payload.get("verification_reason") or payload.get("stderr") or "run failed",
        "artifacts": payload.get("artifacts"),
    }


def list_recent_artifacts(limit: int = 5, tui_runs_dir: Path = TUI_RUNS_DIR, queue_dir: Path = QUEUE_DIR, email_turns_dir: Path = EMAIL_TURNS_DIR) -> list[dict]:
    rows: list[tuple[float, dict]] = []

    if tui_runs_dir.exists():
        run_dirs = [p for p in tui_runs_dir.iterdir() if p.is_dir() and p.name != "queue"]
        for run_dir in run_dirs:
            summary_path = run_dir / "tui_summary.json"
            if summary_path.exists():
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                rows.append((summary_path.stat().st_mtime, {"kind": summary.get("kind", "run"), "path": str(summary_path), "summary": summary}))
            else:
                rows.append((run_dir.stat().st_mtime, {"kind": "run_dir", "path": str(run_dir)}))

    if queue_dir.exists():
        for path in queue_dir.glob("*_summary.json"):
            summary = json.loads(path.read_text(encoding="utf-8"))
            rows.append((path.stat().st_mtime, {"kind": summary.get("kind", "queue"), "path": str(path), "summary": summary}))

    if email_turns_dir.exists():
        for path in email_turns_dir.rglob("*_summary.json"):
            summary = json.loads(path.read_text(encoding="utf-8"))
            rows.append((path.stat().st_mtime, {"kind": summary.get("kind", "turn_packet"), "path": str(path), "summary": summary}))

    rows.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in rows[:limit]]


def generate_turn_packet(game_id: str, turn: int, move: str, actor: str = "operator", fen: str = "startpos", email_turns_dir: Path = EMAIL_TURNS_DIR) -> dict:
    packet = build_turn_packet(
        game_id=game_id,
        turn=turn,
        actor=actor,
        move=move,
        state={"fen": fen},
        legal_next=[],
    )
    out_dir = email_turns_dir / game_id
    out_path = out_dir / f"turn_{turn}.json"
    attachment_path = serialize_turn_packet(packet, out_path)
    bundle = build_email_bundle(packet, attachment_path)
    summary = {
        "kind": "turn_packet",
        "status": "generated",
        "packet_path": attachment_path,
        "game_id": game_id,
        "turn": turn,
    }
    summary_path = persist_turn_summary(attachment_path, summary)
    return {"packet_path": attachment_path, "packet": packet, "email_bundle": bundle, "summary_path": summary_path}


def run_queue(queue: list[QueueItem], stop_on_fail: bool, queue_id: str, queue_dir: Path = QUEUE_DIR, run_item=queue_run_item) -> dict:
    manifest_path = write_queue_manifest(
        queue_dir / f"{queue_id}.json",
        queue_id=queue_id,
        stop_on_fail=stop_on_fail,
        items=queue,
    )
    receipt_path = process_queue(
        queue_items=queue,
        stop_on_fail=stop_on_fail,
        run_item=run_item,
        receipt_path=queue_dir / f"{queue_id}_receipt.json",
        queue_id=queue_id,
    )
    summary = {
        "kind": "queue",
        "status": "completed",
        "queue_id": queue_id,
        "manifest_path": manifest_path,
        "receipt_path": receipt_path,
    }
    summary["summary_path"] = persist_queue_summary(queue_id, summary, queue_dir=queue_dir)
    return summary




def default_cockpit_session_state() -> dict:
    return {
        "selected_screen": "Dashboard",
        "selected_indices": {name: 0 for name in COCKPIT_SCREENS},
        "loaded_gauntlet": None,
        "queue_items": [],
        "last_action_result": None,
        "last_error": None,
        "last_action_receipt_path": None,
    }


def save_cockpit_session_state(state: dict, state_path: Path = COCKPIT_STATE_PATH) -> str:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return str(state_path)


def load_cockpit_session_state(state_path: Path = COCKPIT_STATE_PATH) -> dict:
    baseline = default_cockpit_session_state()
    if not state_path.exists():
        save_cockpit_session_state(baseline, state_path=state_path)
        return baseline
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    baseline.update({k: v for k, v in payload.items() if k in baseline})
    if not isinstance(baseline.get("selected_indices"), dict):
        baseline["selected_indices"] = {name: 0 for name in COCKPIT_SCREENS}
    for name in COCKPIT_SCREENS:
        baseline["selected_indices"].setdefault(name, 0)
    return baseline


def spec_to_dict(spec: GauntletSpec | None) -> dict | None:
    if spec is None:
        return None
    return {
        "gauntlet_name": spec.gauntlet_name,
        "query": spec.query,
        "max_search_intents": spec.max_search_intents,
        "strict_citation_required": spec.strict_citation_required,
        "dry_run": spec.dry_run,
        "require_verify_pass": spec.require_verify_pass,
    }


def dict_to_spec(payload: dict | None) -> GauntletSpec | None:
    if not payload:
        return None
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

def summarize_loaded_gauntlet(spec: GauntletSpec | None) -> dict | None:
    if spec is None:
        return None
    return {
        "gauntlet_name": spec.gauntlet_name,
        "query": spec.query,
        "max_search_intents": spec.max_search_intents,
        "strict_citation_required": spec.strict_citation_required,
        "dry_run": spec.dry_run,
        "require_verify_pass": spec.require_verify_pass,
    }

def build_dashboard_state(queue_items: list[QueueItem] | None = None, recent_limit: int = 5, tui_runs_dir: Path = TUI_RUNS_DIR, queue_dir: Path = QUEUE_DIR, email_turns_dir: Path = EMAIL_TURNS_DIR) -> dict:
    recent = list_recent_artifacts(limit=recent_limit, tui_runs_dir=tui_runs_dir, queue_dir=queue_dir, email_turns_dir=email_turns_dir)
    queue_count = len(queue_items or [])
    return {
        "screen": "Dashboard",
        "queue_size": queue_count,
        "recent_count": len(recent),
        "recent_kinds": [row.get("kind") for row in recent[:3]],
        "last_recent": recent[0] if recent else None,
    }


def build_presets_state(preset_dir: Path = PRESET_DIR) -> dict:
    presets = list_library_presets(preset_dir)
    return {
        "screen": "Presets",
        "count": len(presets),
        "presets": presets,
    }


def build_queue_state(queue_items: list[QueueItem] | None = None) -> dict:
    items = queue_items or []
    return {
        "screen": "Queue",
        "queue_size": len(items),
        "items": [
            {
                "gauntlet_name": item.gauntlet_name,
                "config_path": item.config_path,
                "command": list(item.command),
            }
            for item in items
        ],
    }


def build_artifacts_state(limit: int = 5, tui_runs_dir: Path = TUI_RUNS_DIR, queue_dir: Path = QUEUE_DIR, email_turns_dir: Path = EMAIL_TURNS_DIR) -> dict:
    recent = list_recent_artifacts(limit=limit, tui_runs_dir=tui_runs_dir, queue_dir=queue_dir, email_turns_dir=email_turns_dir)
    return {
        "screen": "Artifacts",
        "count": len(recent),
        "recent_artifacts": recent,
    }


def build_turn_packets_state(limit: int = 5, email_turns_dir: Path = EMAIL_TURNS_DIR) -> dict:
    rows: list[dict] = []
    if email_turns_dir.exists():
        for path in sorted(email_turns_dir.rglob("turn_*_summary.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            summary = json.loads(path.read_text(encoding="utf-8"))
            rows.append({"path": str(path), "summary": summary})
    return {
        "screen": "Turn Packets",
        "count": len(rows),
        "turn_packets": rows,
    }


def build_cockpit_snapshot(
    queue_items: list[QueueItem] | None = None,
    preset_dir: Path = PRESET_DIR,
    tui_runs_dir: Path = TUI_RUNS_DIR,
    queue_dir: Path = QUEUE_DIR,
    email_turns_dir: Path = EMAIL_TURNS_DIR,
    recent_limit: int = 5,
    loaded_gauntlet: GauntletSpec | None = None,
    selected_screen: str = "Dashboard",
    selected_indices: dict[str, int] | None = None,
    last_action_result: dict | None = None,
    last_error: str | None = None,
    session_state_path: str | None = None,
    last_action_receipt_path: str | None = None,
) -> dict:
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "screens": COCKPIT_SCREENS,
        "roots": {
            "preset_dir": str(preset_dir),
            "tui_runs_dir": str(tui_runs_dir),
            "queue_dir": str(queue_dir),
            "email_turns_dir": str(email_turns_dir),
        },
        "cockpit": {
            "session_state_path": session_state_path,
            "selected_screen": selected_screen,
            "selected_indices": selected_indices or {},
            "loaded_gauntlet": summarize_loaded_gauntlet(loaded_gauntlet),
            "last_action_result": last_action_result,
            "last_error": last_error,
            "last_action_receipt_path": last_action_receipt_path,
        },
        "dashboard": build_dashboard_state(queue_items=queue_items, recent_limit=recent_limit, tui_runs_dir=tui_runs_dir, queue_dir=queue_dir, email_turns_dir=email_turns_dir),
        "presets": build_presets_state(preset_dir=preset_dir),
        "queue": build_queue_state(queue_items=queue_items),
        "artifacts": build_artifacts_state(limit=recent_limit, tui_runs_dir=tui_runs_dir, queue_dir=queue_dir, email_turns_dir=email_turns_dir),
        "turn_packets": build_turn_packets_state(limit=recent_limit, email_turns_dir=email_turns_dir),
    }

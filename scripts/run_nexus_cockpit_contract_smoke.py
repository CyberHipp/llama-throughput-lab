#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TUI = REPO_ROOT / "scripts/run_nexus_tui.py"
VALIDATOR = REPO_ROOT / "scripts/validate_nexus_cockpit_contract.py"


def _run_json(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    return proc.returncode, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Cockpit v2 contract smoke and persist evidence bundle")
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "artifacts/nexus/cockpit_contract_smoke"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("smoke-%Y%m%dT%H%M%SZ"))
    args = parser.parse_args(argv)

    run_dir = Path(args.artifact_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    session_path = run_dir / "session.json"
    receipts_dir = run_dir / "receipts"

    errors: list[str] = []

    snapshot_rc, snapshot_payload = _run_json([sys.executable, str(TUI), "--dump-state", "--session-path", str(session_path), "--receipts-dir", str(receipts_dir)])
    snapshot_path = run_dir / "snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if snapshot_rc != 0:
        errors.append("snapshot command failed")

    action = {"action": "load_preset", "source": "library", "selection": "1", "topic": "contract smoke"}
    action_cmd = [
        sys.executable,
        str(TUI),
        "--action-json",
        json.dumps(action),
        "--session-path",
        str(session_path),
        "--receipts-dir",
        str(receipts_dir),
    ]
    env = {**dict(**__import__("os").environ), "PYTHONUNBUFFERED": "1"}
    action_proc = subprocess.run(
        action_cmd,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    action_payload = json.loads(action_proc.stdout.strip().splitlines()[-1]) if action_proc.stdout.strip() else {}
    action_result_path = run_dir / "action_result.json"
    action_result_path.write_text(json.dumps(action_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if action_proc.returncode != 0:
        errors.append("action command failed")

    receipt_src = Path(action_payload.get("receipt_path", "")) if action_payload else Path("")
    receipt_path = run_dir / "receipt.json"
    if receipt_src.exists():
        shutil.copyfile(receipt_src, receipt_path)
    else:
        errors.append("receipt file missing from action result")

    validate_outputs: dict[str, dict] = {}
    validate_targets = {
        "snapshot": snapshot_path,
        "result": action_result_path,
        "receipt": receipt_path,
    }
    for kind, path in validate_targets.items():
        rc, payload = _run_json([sys.executable, str(VALIDATOR), "--kind", kind, "--json-file", str(path)])
        validate_outputs[kind] = payload
        (run_dir / f"validate_{kind}.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        if rc != 0:
            errors.append(f"validate {kind} failed")

    validated = all(validate_outputs.get(k, {}).get("status") == "ok" for k in ("snapshot", "result", "receipt"))
    if not validated:
        errors.append("one or more validations did not report ok")

    summary = {
        "status": "ok" if validated and not errors else "error",
        "run_id": args.run_id,
        "artifact_dir": str(run_dir),
        "snapshot_path": str(snapshot_path),
        "action_result_path": str(action_result_path),
        "receipt_path": str(receipt_src),
        "validated": validated,
        "errors": errors,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import request

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE = REPO_ROOT / "scripts/run_nexus_cockpit_bridge.py"
VALIDATOR = REPO_ROOT / "scripts/validate_nexus_cockpit_contract.py"


def _run_json_cmd(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True)
    payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    return proc.returncode, payload


def _request_json(method: str, url: str, payload: dict | None = None) -> tuple[int, dict]:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url=url, data=body, headers=headers, method=method)
    with request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _find_ephemeral_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_healthz(base_url: str, timeout_s: float = 5.0) -> dict:
    start = time.time()
    last_error: str | None = None
    while time.time() - start < timeout_s:
        try:
            status, payload = _request_json("GET", base_url + "/healthz")
            if status == 200:
                return payload
            last_error = f"unexpected status {status}"
        except Exception as exc:  # pragma: no cover
            last_error = str(exc)
        time.sleep(0.1)
    raise RuntimeError(f"bridge failed to start: {last_error or 'no response'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Cockpit bridge smoke harness and persist evidence bundle")
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "artifacts/nexus/cockpit_bridge_smoke"))
    parser.add_argument("--run-id", default=datetime.now(timezone.utc).strftime("bridge-smoke-%Y%m%dT%H%M%SZ"))
    args = parser.parse_args(argv)

    run_dir = Path(args.artifact_root) / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    session_path = run_dir / "session.json"
    receipts_dir = run_dir / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)

    port = _find_ephemeral_port()
    bridge_cmd = [
        sys.executable,
        str(BRIDGE),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--session-path",
        str(session_path),
        "--receipts-dir",
        str(receipts_dir),
    ]

    errors: list[str] = []
    base_url = f"http://127.0.0.1:{port}"
    bridge_proc = subprocess.Popen(bridge_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    health_payload: dict = {}
    capabilities_payload: dict = {}
    action_specs_payload: dict = {}
    snapshot_payload: dict = {}
    action_result_payload: dict = {}
    receipts_payload: dict = {}
    receipt_payload: dict = {}

    try:
        try:
            health_payload = _wait_for_healthz(base_url)
        except Exception as exc:
            errors.append(str(exc))

        if not errors:
            _, capabilities_payload = _request_json("GET", base_url + "/capabilities")
            _, action_specs_payload = _request_json("GET", base_url + "/action-specs")
            _, snapshot_payload = _request_json("GET", base_url + "/snapshot")
            action_body = {"action": "load_preset", "source": "library", "selection": "1", "topic": "bridge smoke"}
            _, action_result_payload = _request_json("POST", base_url + "/action", action_body)
            _, receipts_payload = _request_json("GET", base_url + "/receipts")
            receipt_name = receipts_payload.get("receipts", [None])[0]
            if not receipt_name:
                errors.append("no receipt emitted")
            else:
                _, receipt_payload = _request_json("GET", base_url + f"/receipts/{receipt_name}")

        healthz_path = run_dir / "healthz.json"
        capabilities_path = run_dir / "capabilities.json"
        action_specs_path = run_dir / "action_specs.json"
        snapshot_path = run_dir / "snapshot.json"
        action_result_path = run_dir / "action_result.json"
        receipts_path = run_dir / "receipts.json"
        receipt_path = run_dir / "receipt.json"

        healthz_path.write_text(json.dumps(health_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        capabilities_path.write_text(json.dumps(capabilities_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        action_specs_path.write_text(json.dumps(action_specs_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        snapshot_path.write_text(json.dumps(snapshot_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        action_result_path.write_text(json.dumps(action_result_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        receipts_path.write_text(json.dumps(receipts_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        receipt_path.write_text(json.dumps(receipt_payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")

        validations: dict[str, dict] = {}
        for kind, path in (
            ("capabilities", capabilities_path),
            ("action_specs", action_specs_path),
            ("snapshot", snapshot_path),
            ("result", action_result_path),
            ("receipt", receipt_path),
        ):
            rc, payload = _run_json_cmd([sys.executable, str(VALIDATOR), "--kind", kind, "--json-file", str(path)])
            validations[kind] = payload
            (run_dir / f"validate_{kind}.json").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            if rc != 0:
                errors.append(f"validate {kind} failed")

        validated = all(
            validations.get(k, {}).get("status") == "ok"
            for k in ("capabilities", "action_specs", "snapshot", "result", "receipt")
        )
        if not validated:
            errors.append("one or more validations did not report ok")

        summary = {
            "status": "ok" if not errors and validated else "error",
            "run_id": args.run_id,
            "artifact_dir": str(run_dir),
            "healthz_path": str(healthz_path),
            "capabilities_path": str(capabilities_path),
            "action_specs_path": str(action_specs_path),
            "snapshot_path": str(snapshot_path),
            "action_result_path": str(action_result_path),
            "receipts_path": str(receipts_path),
            "receipt_path": str(receipt_path),
            "validated": validated,
            "errors": errors,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, sort_keys=True))
        return 0 if summary["status"] == "ok" else 1
    finally:
        bridge_proc.terminate()
        try:
            bridge_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover
            bridge_proc.kill()
            bridge_proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())

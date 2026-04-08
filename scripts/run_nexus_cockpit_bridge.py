#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_nexus_tui

BRIDGE_VERSION = "nexus-cockpit-bridge-v1"
ALLOWED_ACTIONS = {"load_preset", "preview", "show_recent_artifacts", "generate_turn_packet"}


def _run_tui_json(args: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = run_nexus_tui.main(args)
    lines = [line for line in buf.getvalue().splitlines() if line.strip()]
    payload = json.loads(lines[-1]) if lines else {}
    return rc, payload


def _json(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def make_handler(session_path: Path, receipts_dir: Path, receipt_limit: int = 20):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args, **_kwargs):
            return

        def _snapshot_args(self) -> list[str]:
            return ["--session-path", str(session_path), "--receipts-dir", str(receipts_dir)]

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                return _json(self, HTTPStatus.OK, {"status": "ok", "bridge_version": BRIDGE_VERSION})

            if parsed.path == "/snapshot":
                rc, payload = _run_tui_json(["--dump-state", *self._snapshot_args()])
                return _json(self, HTTPStatus.OK if rc == 0 else HTTPStatus.BAD_REQUEST, payload)

            if parsed.path == "/receipts":
                receipts_dir.mkdir(parents=True, exist_ok=True)
                files = sorted(receipts_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:receipt_limit]
                return _json(self, HTTPStatus.OK, {"status": "ok", "receipts": [p.name for p in files]})

            if parsed.path.startswith("/receipts/"):
                name = parsed.path.split("/receipts/", 1)[1]
                if not name or "/" in name or ".." in name:
                    return _json(self, HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid receipt name"})
                path = receipts_dir / Path(name).name
                if not path.exists():
                    return _json(self, HTTPStatus.NOT_FOUND, {"status": "error", "error": "receipt not found"})
                payload = json.loads(path.read_text(encoding="utf-8"))
                return _json(self, HTTPStatus.OK, payload)

            return _json(self, HTTPStatus.NOT_FOUND, {"status": "error", "error": "not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path != "/action":
                return _json(self, HTTPStatus.NOT_FOUND, {"status": "error", "error": "not found"})

            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                action_payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                return _json(self, HTTPStatus.BAD_REQUEST, {"status": "error", "error": "invalid json"})

            action = action_payload.get("action")
            if action not in ALLOWED_ACTIONS:
                return _json(self, HTTPStatus.FORBIDDEN, {"status": "error", "error": f"action not allowed: {action}"})

            rc, payload = _run_tui_json(["--action-json", json.dumps(action_payload), *self._snapshot_args()])
            return _json(self, HTTPStatus.OK if rc == 0 else HTTPStatus.BAD_REQUEST, payload)

    return Handler


def build_server(host: str, port: int, session_path: Path, receipts_dir: Path) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(session_path=session_path, receipts_dir=receipts_dir))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run local-only NEXUS cockpit bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--session-path", default=str(Path("artifacts/nexus/cockpit_state/session.json")))
    parser.add_argument("--receipts-dir", default=str(Path("artifacts/nexus/cockpit_state/receipts")))
    args = parser.parse_args(argv)

    server = build_server(args.host, args.port, Path(args.session_path), Path(args.receipts_dir))
    print(json.dumps({"status": "ok", "bridge_version": BRIDGE_VERSION, "host": args.host, "port": args.port}, sort_keys=True))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

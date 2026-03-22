from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def is_executable_reference(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    if path.is_file() and os.access(path, os.X_OK):
        return True
    return shutil.which(value) is not None


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def wait_for_server_ready(host: str, port: int, timeout_s: int) -> None:
    deadline = time.time() + timeout_s
    last_error: Exception | None = None
    health_url = f"http://{host}:{port}/health"
    models_url = f"http://{host}:{port}/v1/models"

    while time.time() < deadline:
        for url in (health_url, models_url):
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        resp.read()
                        return
            except urllib.error.HTTPError as exc:
                if exc.code in {200, 404}:
                    return
                last_error = exc
            except Exception as exc:  # pragma: no cover - exercised via retry behavior
                last_error = exc
        time.sleep(0.5)

    raise RuntimeError(
        f"Server did not become ready at {host}:{port} within {timeout_s}s: {last_error}"
    )


def post_json(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Connection": "close"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        with exc:
            data = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP error {exc.code}: {data}") from exc


def launch_server_process(
    command: list[str],
    stdout_path: str,
    stderr_path: str,
    env_overlay: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    stdout_handle = Path(stdout_path).open("w", encoding="utf-8")
    stderr_handle = Path(stderr_path).open("w", encoding="utf-8")
    env = None
    if env_overlay:
        env = dict(os.environ)
        env.update(env_overlay)
    process = subprocess.Popen(
        command,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
        env=env,
    )
    setattr(process, "_stdout_handle", stdout_handle)
    setattr(process, "_stderr_handle", stderr_handle)
    return process


def stop_server_process(process: subprocess.Popen[str], timeout_s: int = 10) -> int:
    process.terminate()
    try:
        code = process.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        process.kill()
        code = process.wait(timeout=5)

    stdout_handle = getattr(process, "_stdout_handle", None)
    stderr_handle = getattr(process, "_stderr_handle", None)
    if stdout_handle:
        stdout_handle.close()
    if stderr_handle:
        stderr_handle.close()
    return code


def extract_token_count(response: dict[str, Any]) -> int:
    timings = response.get("timings") or {}
    for key in ("predicted_n", "tokens_predicted", "completion_tokens"):
        if key in timings:
            return int(timings[key])
        if key in response:
            return int(response[key])
    usage = response.get("usage") or {}
    if "completion_tokens" in usage:
        return int(usage["completion_tokens"])
    return 0


def extract_tokens_per_second(response: dict[str, Any]) -> float | None:
    timings = response.get("timings") or {}
    for key in ("predicted_per_second", "tokens_per_second"):
        if key in timings:
            return float(timings[key])

    predicted_n = timings.get("predicted_n")
    predicted_ms = timings.get("predicted_ms")
    if predicted_n and predicted_ms:
        return float(predicted_n) / (float(predicted_ms) / 1000.0)

    return None

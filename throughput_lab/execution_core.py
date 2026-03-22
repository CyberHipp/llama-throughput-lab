from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from throughput_lab.runtime_service import (
    extract_token_count,
    extract_tokens_per_second,
    is_executable_reference,
    is_port_available,
    launch_server_process,
    post_json,
    stop_server_process,
    wait_for_server_ready,
)


class TopologyMode(str, Enum):
    SINGLE = "single"
    CONCURRENT = "concurrent"
    ROUND_ROBIN = "round_robin"


class EndpointMode(str, Enum):
    COMPLETION = "/completion"
    V1_COMPLETIONS = "/v1/completions"
    CHAT_COMPLETIONS = "/v1/chat/completions"


class VerificationMode(str, Enum):
    NON_EMPTY = "NON_EMPTY"
    EXACT = "EXACT"
    CONTAINS = "CONTAINS"


@dataclass(frozen=True)
class RunConfig:
    model_path: str
    llama_server_bin: str
    host: str = "127.0.0.1"
    port: int = 8080
    topology_mode: TopologyMode = TopologyMode.SINGLE
    ctx_size: int | None = None
    ctx_size_per_session: int | None = None
    parallel: int = 1
    concurrency: int = 1
    threads: int | None = None
    threads_http: int | None = None
    batch: int | None = None
    ubatch: int | None = None
    n_predict: int = 128
    temperature: float = 0.3
    seed: int | None = None
    system_prompt: str | None = None
    prompt: str = "Share three optimization tips for model serving."
    stop_tokens: tuple[str, ...] = field(default_factory=tuple)
    startup_delay_s: float = 0.0
    bind_timeout_s: int = 180
    ready_timeout_s: int = 120
    extra_llama_server_args: tuple[str, ...] = field(default_factory=tuple)
    runtime_env: dict[str, str] = field(default_factory=dict)
    endpoint_mode: EndpointMode = EndpointMode.COMPLETION
    request_model: str | None = None
    verification_mode: VerificationMode = VerificationMode.NON_EMPTY
    expected_text: str | None = None

    @staticmethod
    def _parse_extra_args(raw: str) -> tuple[str, ...]:
        if not raw:
            return ()
        if "," in raw:
            return tuple(token.strip() for token in raw.split(",") if token.strip())
        return tuple(token for token in raw.split(" ") if token)

    @staticmethod
    def _parse_stop_tokens(raw: str) -> tuple[str, ...]:
        if not raw:
            return ()
        return tuple(item for item in (part.strip() for part in raw.split(",")) if item)

    @staticmethod
    def _parse_runtime_env(raw: str) -> dict[str, str]:
        if not raw:
            return {}
        pairs: dict[str, str] = {}
        for token in raw.split(","):
            token = token.strip()
            if not token:
                continue
            if "=" not in token:
                raise ValueError(f"Invalid runtime env token '{token}'. Expected KEY=VALUE format.")
            key, value = token.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"Invalid runtime env token '{token}'. Key cannot be empty.")
            pairs[key] = value
        return pairs

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "RunConfig":
        env_map = dict(os.environ if env is None else env)

        parallel = int(env_map.get("LLAMA_PARALLEL", "1"))
        n_predict = int(env_map.get("LLAMA_N_PREDICT", "128"))
        ctx_per = env_map.get("LLAMA_CTXSIZE_PER_SESSION")
        ctx_per_value = int(ctx_per) if ctx_per else n_predict
        ctx_size = ctx_per_value * parallel

        endpoint_raw = env_map.get("LLAMA_ENDPOINT_MODE", EndpointMode.COMPLETION.value)
        try:
            endpoint_mode = EndpointMode(endpoint_raw)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported LLAMA_ENDPOINT_MODE '{endpoint_raw}'. "
                "Allowed: "
                f"{EndpointMode.COMPLETION.value}, "
                f"{EndpointMode.V1_COMPLETIONS.value}, "
                f"{EndpointMode.CHAT_COMPLETIONS.value}."
            ) from exc

        topology_raw = env_map.get("LLAMA_TOPOLOGY_MODE", TopologyMode.SINGLE.value)
        topology = TopologyMode(topology_raw)

        verification_raw = env_map.get("LLAMA_VERIFY_MODE", VerificationMode.NON_EMPTY.value)
        try:
            verification_mode = VerificationMode(verification_raw)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported LLAMA_VERIFY_MODE '{verification_raw}'. "
                f"Allowed: {VerificationMode.NON_EMPTY.value}, {VerificationMode.EXACT.value}, {VerificationMode.CONTAINS.value}."
            ) from exc

        return cls(
            model_path=env_map.get("LLAMA_MODEL_PATH", ""),
            llama_server_bin=env_map.get("LLAMA_SERVER_BIN", "llama-server"),
            host=env_map.get("LLAMA_SERVER_HOST", "127.0.0.1"),
            port=int(env_map.get("LLAMA_SERVER_PORT", "8080")),
            topology_mode=topology,
            ctx_size=ctx_size,
            ctx_size_per_session=int(ctx_per) if ctx_per else None,
            parallel=parallel,
            concurrency=int(env_map.get("LLAMA_CONCURRENCY", "1")),
            threads=int(env_map["LLAMA_THREADS"]) if env_map.get("LLAMA_THREADS") else None,
            threads_http=int(env_map["LLAMA_THREADS_HTTP"]) if env_map.get("LLAMA_THREADS_HTTP") else None,
            batch=int(env_map["LLAMA_BATCH"]) if env_map.get("LLAMA_BATCH") else None,
            ubatch=int(env_map["LLAMA_UBATCH"]) if env_map.get("LLAMA_UBATCH") else None,
            n_predict=n_predict,
            temperature=float(env_map.get("LLAMA_TEMPERATURE", "0.3")),
            seed=int(env_map["LLAMA_SEED"]) if env_map.get("LLAMA_SEED") else None,
            system_prompt=env_map.get("LLAMA_SYSTEM_PROMPT"),
            prompt=env_map.get("LLAMA_PROMPT", "Share three optimization tips for model serving."),
            stop_tokens=cls._parse_stop_tokens(env_map.get("LLAMA_STOP_TOKENS", "")),
            startup_delay_s=float(env_map.get("LLAMA_STARTUP_DELAY_S", "0.0")),
            bind_timeout_s=int(env_map.get("LLAMA_SERVER_BIND_TIMEOUT", "180")),
            ready_timeout_s=int(env_map.get("LLAMA_READY_TIMEOUT", "120")),
            extra_llama_server_args=cls._parse_extra_args(env_map.get("LLAMA_SERVER_ARGS", "")),
            runtime_env=cls._parse_runtime_env(env_map.get("LLAMA_RUNTIME_ENV", "")),
            endpoint_mode=endpoint_mode,
            request_model=env_map.get("LLAMA_REQUEST_MODEL"),
            verification_mode=verification_mode,
            expected_text=env_map.get("LLAMA_EXPECTED_TEXT"),
        )

    def endpoint_path(self) -> str:
        return self.endpoint_mode.value

    def validate_for_single_smoke(self) -> None:
        if self.topology_mode != TopologyMode.SINGLE:
            raise ValueError(
                "This core path currently enforces single-node smoke mode only "
                "(LLAMA_TOPOLOGY_MODE=single)."
            )

    def build_server_command(self) -> list[str]:
        cmd = [
            self.llama_server_bin,
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--model",
            self.model_path,
        ]

        extra = list(self.extra_llama_server_args)
        if not _contains_flag(extra, "--parallel"):
            cmd += ["--parallel", str(self.parallel)]
        if not _contains_flag(extra, "--ctx-size") and self.ctx_size is not None:
            cmd += ["--ctx-size", str(self.ctx_size)]

        if self.threads is not None:
            cmd += ["--threads", str(self.threads)]
        if self.threads_http is not None:
            cmd += ["--threads-http", str(self.threads_http)]
        if self.batch is not None:
            cmd += ["--batch-size", str(self.batch)]
        if self.ubatch is not None:
            cmd += ["--ubatch", str(self.ubatch)]

        cmd += extra
        return cmd

    def build_request_payload(self) -> dict[str, Any]:
        stop = list(self.stop_tokens) if self.stop_tokens else None

        if self.endpoint_mode == EndpointMode.COMPLETION:
            if self.system_prompt:
                raise ValueError(
                    "system_prompt is not supported for /completion mode in this core path; "
                    "use /v1/chat/completions instead."
                )
            payload: dict[str, Any] = {
                "prompt": self.prompt,
                "n_predict": self.n_predict,
                "temperature": self.temperature,
                "stream": False,
            }
            if self.seed is not None:
                payload["seed"] = self.seed
            if stop is not None:
                payload["stop"] = stop
            return payload

        if not self.request_model:
            raise ValueError(
                f"request_model is required for {self.endpoint_mode.value} endpoint mode."
            )

        if self.endpoint_mode == EndpointMode.V1_COMPLETIONS:
            payload = {
                "model": self.request_model,
                "prompt": self.prompt,
                "max_tokens": self.n_predict,
                "temperature": self.temperature,
                "stream": False,
            }
            if self.seed is not None:
                payload["seed"] = self.seed
            if stop is not None:
                payload["stop"] = stop
            return payload

        payload = {
            "model": self.request_model,
            "messages": [
                *(
                    [{"role": "system", "content": self.system_prompt}]
                    if self.system_prompt
                    else []
                ),
                {"role": "user", "content": self.prompt},
            ],
            "max_tokens": self.n_predict,
            "temperature": self.temperature,
            "stream": False,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        if stop is not None:
            payload["stop"] = stop
        return payload


@dataclass(frozen=True)
class RunResult:
    run_id: str
    receipt_path: str
    stdout_path: str
    stderr_path: str
    exit_code_path: str
    exit_code: int


@dataclass(frozen=True)
class SmokeResult(RunResult):
    response_path: str
    request_path: str
    overall_verification_pass: bool


def _contains_flag(args: list[str], flag: str) -> bool:
    return any(item == flag or item.startswith(flag + "=") for item in args)


def _git_commit(default: str = "UNKNOWN") -> str:
    try:
        value = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        return value or default
    except Exception:
        return default


def parse_smoke_response(endpoint_mode: EndpointMode, payload: dict[str, Any]) -> str:
    if endpoint_mode == EndpointMode.COMPLETION:
        text = payload.get("content") or payload.get("response") or payload.get("text")
        if isinstance(text, str) and text.strip():
            return text
        raise ValueError("Unable to parse non-empty response text from /completion payload.")

    if endpoint_mode == EndpointMode.V1_COMPLETIONS:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            text = (choices[0] or {}).get("text")
            if isinstance(text, str) and text.strip():
                return text
        raise ValueError("Unable to parse non-empty response text from /v1/completions payload.")

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] or {}
        message = choice.get("message") or {}
        text = message.get("content")
        if isinstance(text, str) and text.strip():
            return text
    raise ValueError("Unable to parse non-empty response text from /v1/chat/completions payload.")


def verify_smoke_response(text: str, mode: VerificationMode, expected_text: str | None) -> tuple[bool, str]:
    if mode == VerificationMode.NON_EMPTY:
        return (bool(text.strip()), "response text is empty" if not text.strip() else "ok")

    if expected_text is None:
        return (False, f"verification mode {mode.value} requires expected_text")

    if mode == VerificationMode.EXACT:
        return (text == expected_text, "exact mismatch" if text != expected_text else "ok")

    if mode == VerificationMode.CONTAINS:
        return (expected_text in text, "substring not found" if expected_text not in text else "ok")

    return (False, "unsupported verification mode")


def run_preflight_checks(config: RunConfig) -> dict[str, Any]:
    checks = []

    model_ok = bool(config.model_path) and Path(config.model_path).is_file()
    checks.append({"name": "model_path_exists", "result": "pass" if model_ok else "fail"})

    llama_ok = is_executable_reference(config.llama_server_bin)
    checks.append({"name": "llama_server_bin_executable", "result": "pass" if llama_ok else "fail"})

    try:
        config.validate_for_single_smoke()
        topology_ok = True
    except Exception:
        topology_ok = False
    checks.append({"name": "topology_allowed_for_smoke", "result": "pass" if topology_ok else "fail"})

    port_ok = is_port_available(config.host, config.port)
    checks.append({"name": "target_port_available", "result": "pass" if port_ok else "fail"})

    request_model_ok = True
    if config.endpoint_mode in {EndpointMode.V1_COMPLETIONS, EndpointMode.CHAT_COMPLETIONS}:
        request_model_ok = bool(config.request_model)
    checks.append(
        {
            "name": "request_model_compatibility",
            "result": "pass" if request_model_ok else "fail",
        }
    )

    expected_text_ok = True
    if config.verification_mode in {VerificationMode.EXACT, VerificationMode.CONTAINS}:
        expected_text_ok = bool(config.expected_text)
    checks.append(
        {
            "name": "verification_expected_text_compatibility",
            "result": "pass" if expected_text_ok else "fail",
        }
    )

    try:
        config.build_request_payload()
        payload_buildable = True
    except Exception:
        payload_buildable = False
    checks.append(
        {
            "name": "request_payload_buildable",
            "result": "pass" if payload_buildable else "fail",
        }
    )

    all_pass = all(item["result"] == "pass" for item in checks)
    return {"checks": checks, "result": "pass" if all_pass else "fail"}


def _classify_controlled_shutdown(exit_code: int, intentional_stop: bool, request_ok: bool) -> tuple[bool, str]:
    if not intentional_stop:
        return False, "no_intentional_stop"
    if not request_ok:
        return False, "request_not_successful"

    # For intentionally terminated long-running services, signal exits are expected.
    if exit_code in {0, -15, 143}:
        return True, "controlled_stop"
    return False, f"unexpected_exit_code_{exit_code}"


def _write_structured_failure_receipt(
    *,
    output_dir: str | Path,
    intent: str,
    tool_name: str,
    pinned_commit: str | None,
    config: RunConfig | None,
    failure_summary: str,
) -> tuple[dict[str, Any], Path]:
    run_id = os.environ.get("RUN_ID") or uuid.uuid4().hex
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    paths = _artifact_paths(run_id, output_dir)
    receipt_path = Path(paths["receipt_artifact_path"])
    Path(paths["response_artifact_path"]).write_text(
        json.dumps({"error": failure_summary}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(paths["request_artifact_path"]).write_text("{}\n", encoding="utf-8")
    Path(paths["exit_code_artifact_path"]).write_text("-1\n", encoding="utf-8")

    receipt = {
        "RUN_ID": run_id,
        "TIMESTAMP_UTC": timestamp_utc,
        "INTENT": intent,
        "TOOL_NAME": tool_name,
        "PINNED_COMMIT": pinned_commit or _git_commit(),
        "resolved_command": [],
        "resolved_endpoint_path": None,
        "resolved_request_payload": {},
        "resolved_topology": config.topology_mode.value if config else "unknown",
        "resolved_model_path": config.model_path if config else "",
        "resolved_llama_server_path": config.llama_server_bin if config else "",
        "resolved_runtime_env": dict(config.runtime_env) if config else {},
        "verification_mode": config.verification_mode.value if config else VerificationMode.NON_EMPTY.value,
        "expected_text": config.expected_text if config else None,
        "preflight_verification_result": "fail",
        "readiness_verification_result": "fail",
        "response_parse_result": "fail",
        "semantic_verification_result": "fail",
        "request_verification_result": "fail",
        "overall_verification_result": "fail",
        "verification_result": "fail",
        "response_summary": {
            "elapsed_wall_time_s": 0.0,
            "token_count": 0,
            "tokens_per_second": None,
            "request_success": False,
            "response_text_present": False,
        },
        "extracted_response_text_preview": "",
        "failure_summary": failure_summary,
        "next_step": "Fix config/preflight issue and retry dry-run before smoke.",
        **paths,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt, receipt_path


def _stable_envelope(
    *,
    mode: str,
    status: str,
    run_id: str,
    timestamp_utc: str,
    intent: str,
    tool_name: str,
    receipt_path: str | None,
    data: dict[str, Any],
    failure_summary: str,
    next_step: str,
) -> dict[str, Any]:
    return {
        "packet_version": "1.0",
        "mode": mode,
        "status": status,
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "intent": intent,
        "tool_name": tool_name,
        "receipt_path": receipt_path,
        "failure_summary": failure_summary,
        "next_step": next_step,
        "data": data,
    }


def dry_run_packet(
    config: RunConfig,
    *,
    output_dir: str | Path,
    intent: str,
    tool_name: str = "llama-throughput-lab",
    pinned_commit: str | None = None,
) -> tuple[dict[str, Any], int]:
    run_id = os.environ.get("RUN_ID") or uuid.uuid4().hex
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        plan = build_run_plan(
            config,
            output_dir=output_dir,
            intent=intent,
            tool_name=tool_name,
            pinned_commit=pinned_commit,
            run_id=run_id,
        )
        envelope = _stable_envelope(
            mode="dry-run",
            status="success",
            run_id=run_id,
            timestamp_utc=timestamp_utc,
            intent=intent,
            tool_name=tool_name,
            receipt_path=None,
            data={"plan": plan},
            failure_summary="none",
            next_step="Run --preflight-only or --single-smoke.",
        )
        return envelope, 0
    except Exception as exc:
        envelope = _stable_envelope(
            mode="dry-run",
            status="failure",
            run_id=run_id,
            timestamp_utc=timestamp_utc,
            intent=intent,
            tool_name=tool_name,
            receipt_path=None,
            data={"error_type": exc.__class__.__name__},
            failure_summary=str(exc).split("\n", 1)[0][:240],
            next_step="Fix contract inputs and retry --dry-run.",
        )
        return envelope, 1


def preflight_packet(
    config: RunConfig,
    *,
    output_dir: str | Path,
    intent: str,
    tool_name: str = "llama-throughput-lab",
) -> tuple[dict[str, Any], int]:
    run_id = os.environ.get("RUN_ID") or uuid.uuid4().hex
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    checks = run_preflight_checks(config)
    ok = checks["result"] == "pass"
    envelope = _stable_envelope(
        mode="preflight-only",
        status="success" if ok else "failure",
        run_id=run_id,
        timestamp_utc=timestamp_utc,
        intent=intent,
        tool_name=tool_name,
        receipt_path=None,
        data={"preflight": checks, "resolved_runtime_env": dict(config.runtime_env)},
        failure_summary="none" if ok else "preflight checks failed",
        next_step="Run --single-smoke." if ok else "Fix preflight failures before smoke.",
    )
    return envelope, 0 if ok else 1


def _artifact_paths(run_id: str, output_dir: str | Path) -> dict[str, str]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return {
        "stdout_artifact_path": str(out_dir / f"{run_id}.stdout.log"),
        "stderr_artifact_path": str(out_dir / f"{run_id}.stderr.log"),
        "request_artifact_path": str(out_dir / f"{run_id}.request.json"),
        "response_artifact_path": str(out_dir / f"{run_id}.response.json"),
        "exit_code_artifact_path": str(out_dir / f"{run_id}.exit_code"),
        "receipt_artifact_path": str(out_dir / f"{run_id}.receipt.json"),
    }


def build_run_plan(
    config: RunConfig,
    *,
    output_dir: str | Path,
    intent: str,
    tool_name: str = "llama-throughput-lab",
    pinned_commit: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    config.validate_for_single_smoke()

    resolved_run_id = run_id or os.environ.get("RUN_ID") or uuid.uuid4().hex
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    paths = _artifact_paths(resolved_run_id, output_dir)

    preflight_targets = [
        "model_path_exists",
        "llama_server_bin_executable",
        "topology_allowed_for_smoke",
        "target_port_available",
        "request_model_compatibility",
        "verification_expected_text_compatibility",
        "request_payload_buildable",
    ]

    return {
        "RUN_ID": resolved_run_id,
        "TIMESTAMP_UTC": timestamp_utc,
        "INTENT": intent,
        "TOOL_NAME": tool_name,
        "PINNED_COMMIT": pinned_commit or _git_commit(),
        "resolved_command": config.build_server_command(),
        "resolved_endpoint_path": config.endpoint_path(),
        "resolved_request_payload": config.build_request_payload(),
        "resolved_request_model": config.request_model,
        "resolved_topology": config.topology_mode.value,
        "resolved_model_path": config.model_path,
        "resolved_llama_server_path": config.llama_server_bin,
        "resolved_ctx_size": config.ctx_size,
        "resolved_parallel": config.parallel,
        "resolved_concurrency": config.concurrency,
        "resolved_runtime_env": dict(config.runtime_env),
        "verification_mode": config.verification_mode.value,
        "expected_text": config.expected_text,
        "preflight_targets": preflight_targets,
        "expected_response_policy": {
            "mode": config.verification_mode.value,
            "expected_text_required": config.verification_mode in {VerificationMode.EXACT, VerificationMode.CONTAINS},
            "request_model_required": config.endpoint_mode in {EndpointMode.V1_COMPLETIONS, EndpointMode.CHAT_COMPLETIONS},
        },
        "expected_artifact_set": [
            "stdout_artifact_path",
            "stderr_artifact_path",
            "request_artifact_path",
            "response_artifact_path",
            "exit_code_artifact_path",
            "receipt_artifact_path",
        ],
        **paths,
        "verification_target": "preflight_pass and readiness_pass and response_parse_pass and semantic_pass and controlled_shutdown_pass",
        "failure_summary": "pending_execution",
        "next_step": "Execute single-node smoke and inspect receipt artifacts.",
        "config_snapshot": asdict(config),
    }


def run_with_receipt(
    config: RunConfig,
    *,
    output_dir: str | Path,
    intent: str,
    tool_name: str = "llama-throughput-lab",
    pinned_commit: str | None = None,
) -> RunResult:
    plan = build_run_plan(
        config,
        output_dir=output_dir,
        intent=intent,
        tool_name=tool_name,
        pinned_commit=pinned_commit,
    )

    cmd = plan["resolved_command"]
    stdout_path = Path(plan["stdout_artifact_path"])
    stderr_path = Path(plan["stderr_artifact_path"])
    exit_code_path = Path(plan["exit_code_artifact_path"])
    receipt_path = Path(plan["receipt_artifact_path"])

    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        proc = subprocess.run(cmd, stdout=stdout_handle, stderr=stderr_handle, text=True, check=False)

    exit_code_path.write_text(f"{proc.returncode}\n", encoding="utf-8")

    verification = "pass" if proc.returncode == 0 else "fail"
    failure_summary = "none" if proc.returncode == 0 else f"llama-server exited with {proc.returncode}"

    receipt = {
        **plan,
        "verification_result": verification,
        "failure_summary": failure_summary,
        "next_step": "Use --single-smoke for full lifecycle verification.",
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return RunResult(
        run_id=plan["RUN_ID"],
        receipt_path=str(receipt_path),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        exit_code_path=str(exit_code_path),
        exit_code=proc.returncode,
    )


def execute_single_smoke_with_receipt(
    config: RunConfig,
    *,
    output_dir: str | Path,
    intent: str,
    tool_name: str = "llama-throughput-lab",
    pinned_commit: str | None = None,
) -> SmokeResult:
    try:
        plan = build_run_plan(
            config,
            output_dir=output_dir,
            intent=intent,
            tool_name=tool_name,
            pinned_commit=pinned_commit,
        )
    except Exception as exc:
        failure_summary = str(exc).split("\n", 1)[0][:240]
        receipt, receipt_path = _write_structured_failure_receipt(
            output_dir=output_dir,
            intent=intent,
            tool_name=tool_name,
            pinned_commit=pinned_commit,
            config=config,
            failure_summary=failure_summary,
        )
        return SmokeResult(
            run_id=receipt["RUN_ID"],
            receipt_path=str(receipt_path),
            stdout_path=receipt["stdout_artifact_path"],
            stderr_path=receipt["stderr_artifact_path"],
            exit_code_path=receipt["exit_code_artifact_path"],
            exit_code=-1,
            response_path=receipt["response_artifact_path"],
            request_path=receipt["request_artifact_path"],
            overall_verification_pass=False,
        )
    start_time = time.time()
    readiness_ok = False
    request_ok = False
    response_parse_ok = False
    semantic_ok = False
    failure_summary = "none"
    response_payload: dict[str, Any] = {}
    extracted_text = ""
    process = None
    server_exit_code = -1

    request_path = Path(plan["request_artifact_path"])
    response_path = Path(plan["response_artifact_path"])
    exit_code_path = Path(plan["exit_code_artifact_path"])
    receipt_path = Path(plan["receipt_artifact_path"])

    preflight = run_preflight_checks(config)
    preflight_ok = preflight["result"] == "pass"

    request_path.write_text(
        json.dumps(plan["resolved_request_payload"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if preflight_ok:
        try:
            process = launch_server_process(
                plan["resolved_command"],
                plan["stdout_artifact_path"],
                plan["stderr_artifact_path"],
                env_overlay=config.runtime_env,
            )
            wait_for_server_ready(config.host, config.port, config.bind_timeout_s)
            readiness_ok = True

            response_payload = post_json(
                f"http://{config.host}:{config.port}{plan['resolved_endpoint_path']}",
                plan["resolved_request_payload"],
                timeout=config.ready_timeout_s,
            )
            request_ok = True
            extracted_text = parse_smoke_response(config.endpoint_mode, response_payload)
            response_parse_ok = True
            semantic_ok, semantic_reason = verify_smoke_response(
                extracted_text,
                config.verification_mode,
                config.expected_text,
            )
            if not semantic_ok:
                failure_summary = semantic_reason

            response_payload = {**response_payload, "extracted_text": extracted_text}
            response_path.write_text(
                json.dumps(response_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            if failure_summary == "none":
                failure_summary = str(exc).split("\n", 1)[0][:240]
            response_path.write_text(
                json.dumps({"error": failure_summary}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        finally:
            if process is not None:
                server_exit_code = stop_server_process(process)
                exit_code_path.write_text(f"{server_exit_code}\n", encoding="utf-8")
            else:
                exit_code_path.write_text("-1\n", encoding="utf-8")
    else:
        failure_summary = "preflight checks failed"
        response_path.write_text(
            json.dumps({"error": failure_summary}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exit_code_path.write_text("-1\n", encoding="utf-8")

    elapsed_s = time.time() - start_time
    token_count = extract_token_count(response_payload) if request_ok else 0
    tokens_per_second = extract_tokens_per_second(response_payload) if request_ok else None
    controlled_shutdown_ok, controlled_shutdown_reason = _classify_controlled_shutdown(
        server_exit_code,
        intentional_stop=process is not None,
        request_ok=request_ok,
    )
    overall_ok = preflight_ok and readiness_ok and response_parse_ok and semantic_ok and controlled_shutdown_ok

    if failure_summary == "none" and not overall_ok:
        failure_summary = "smoke verification failed"

    next_step = (
        "Promote this receipt to operator review and wire into TUI adapter."
        if overall_ok
        else "Inspect preflight/readiness/response artifacts and correct config before retrying smoke."
    )

    response_text_present = bool(extracted_text.strip())
    receipt = {
        **plan,
        "preflight_verification_result": "pass" if preflight_ok else "fail",
        "preflight_checks": preflight["checks"],
        "readiness_verification_result": "pass" if readiness_ok else "fail",
        "response_parse_result": "pass" if response_parse_ok else "fail",
        "semantic_verification_result": "pass" if semantic_ok else "fail",
        "request_verification_result": "pass" if request_ok else "fail",
        "controlled_shutdown_result": "pass" if controlled_shutdown_ok else "fail",
        "controlled_shutdown_reason": controlled_shutdown_reason,
        "overall_verification_result": "pass" if overall_ok else "fail",
        "verification_result": "pass" if overall_ok else "fail",
        "response_summary": {
            "elapsed_wall_time_s": round(elapsed_s, 6),
            "token_count": token_count,
            "tokens_per_second": tokens_per_second,
            "request_success": request_ok,
            "response_text_present": response_text_present,
        },
        "extracted_response_text_preview": extracted_text[:120],
        "failure_summary": failure_summary,
        "next_step": next_step,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return SmokeResult(
        run_id=plan["RUN_ID"],
        receipt_path=str(receipt_path),
        stdout_path=plan["stdout_artifact_path"],
        stderr_path=plan["stderr_artifact_path"],
        exit_code_path=str(exit_code_path),
        exit_code=server_exit_code,
        response_path=str(response_path),
        request_path=str(request_path),
        overall_verification_pass=overall_ok,
    )

#!/usr/bin/env python3
"""Non-interactive execution entrypoint for future TUI/GUI callers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from throughput_lab.execution_core import (
    EndpointMode,
    RunConfig,
    TopologyMode,
    VerificationMode,
    dry_run_packet,
    execute_single_smoke_with_receipt,
    preflight_packet,
    run_with_receipt,
)


def _normalize_config_json_dict(data: dict) -> dict:
    normalized = dict(data)
    if "topology_mode" in normalized:
        normalized["topology_mode"] = TopologyMode(normalized["topology_mode"])
    if "endpoint_mode" in normalized:
        normalized["endpoint_mode"] = EndpointMode(normalized["endpoint_mode"])
    if "verification_mode" in normalized:
        normalized["verification_mode"] = VerificationMode(normalized["verification_mode"])
    if "stop_tokens" in normalized:
        normalized["stop_tokens"] = tuple(normalized["stop_tokens"])
    if "extra_llama_server_args" in normalized:
        normalized["extra_llama_server_args"] = tuple(normalized["extra_llama_server_args"])
    return normalized


def _read_config_json(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Config JSON must be an object: {path}")
    return payload


def _validate_override_keys(base_data: dict, override_data: dict) -> None:
    unknown = sorted(set(override_data.keys()) - set(base_data.keys()))
    if unknown:
        raise ValueError(f"Unknown override key(s): {', '.join(unknown)}")


def _merge_config_dicts(base_data: dict, override_data: dict) -> dict:
    _validate_override_keys(base_data, override_data)
    merged = dict(base_data)
    for key, value in override_data.items():
        merged[key] = value
    return merged


def _stable_cli_envelope(
    *,
    mode: str,
    status: str,
    run_id: str,
    timestamp_utc: str | None,
    intent: str,
    receipt_path: str | None,
    failure_summary: str,
    next_step: str,
    data: dict,
) -> dict:
    return {
        "packet_version": "1.0",
        "mode": mode,
        "status": status,
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "intent": intent,
        "tool_name": "llama-throughput-lab",
        "receipt_path": receipt_path,
        "failure_summary": failure_summary,
        "next_step": next_step,
        "data": data,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run deterministic llama-server execution core job.")
    parser.add_argument("--intent", default="throughput-smoke", help="Operator intent to stamp into receipt")
    parser.add_argument("--output-dir", default="artifacts/receipts", help="Directory for receipt/stdout/stderr artifacts")
    parser.add_argument(
        "--config-json",
        help="Optional JSON file with explicit config fields. If omitted, LLAMA_* env vars are used.",
    )
    parser.add_argument(
        "--config-override-json",
        help=(
            "Optional JSON file with machine-local overrides. "
            "Requires --config-json and fails closed on unknown keys."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print a deterministic run plan packet and exit without executing llama-server.",
    )
    parser.add_argument(
        "--single-smoke",
        action="store_true",
        help="Execute start/wait/request/stop single-node smoke and emit smoke receipt.",
    )
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Run contract preflight checks only and emit machine-readable packet.",
    )
    parser.add_argument(
        "--plan-out",
        help="Optional path to write dry-run packet JSON (works with --dry-run).",
    )
    return parser.parse_args()


def load_config(path: str | None) -> RunConfig:
    if not path:
        return RunConfig.from_env()
    data = _normalize_config_json_dict(_read_config_json(path))
    return RunConfig(**data)


def load_config_with_optional_override(base_path: str | None, override_path: str | None) -> RunConfig:
    if not override_path:
        return load_config(base_path)
    if not base_path:
        raise ValueError("--config-override-json requires --config-json")
    base_raw = _read_config_json(base_path)
    override_raw = _read_config_json(override_path)
    merged_raw = _merge_config_dicts(base_raw, override_raw)
    merged = _normalize_config_json_dict(merged_raw)
    return RunConfig(**merged)


def main() -> int:
    args = parse_args()
    config = load_config_with_optional_override(args.config_json, args.config_override_json)

    if args.dry_run:
        envelope, exit_code = dry_run_packet(config, output_dir=args.output_dir, intent=args.intent)
        rendered = json.dumps(envelope, indent=2, sort_keys=True)
        print(rendered)
        if args.plan_out:
            Path(args.plan_out).write_text(rendered + "\n", encoding="utf-8")
        return exit_code

    if args.preflight_only:
        envelope, exit_code = preflight_packet(config, output_dir=args.output_dir, intent=args.intent)
        rendered = json.dumps(envelope, indent=2, sort_keys=True)
        print(rendered)
        if args.plan_out:
            Path(args.plan_out).write_text(rendered + "\n", encoding="utf-8")
        return exit_code

    if args.single_smoke:
        result = execute_single_smoke_with_receipt(config, output_dir=args.output_dir, intent=args.intent)
        receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
        envelope = _stable_cli_envelope(
            mode="single-smoke",
            status="success" if result.overall_verification_pass else "failure",
            run_id=result.run_id,
            timestamp_utc=receipt.get("TIMESTAMP_UTC"),
            intent=args.intent,
            receipt_path=result.receipt_path,
            failure_summary=receipt.get("failure_summary", "none"),
            next_step=receipt.get("next_step", ""),
            data={
                "response_path": result.response_path,
                "overall_verification_pass": result.overall_verification_pass,
            },
        )
        print(json.dumps(envelope, sort_keys=True))
        return 0 if result.overall_verification_pass else 1

    result = run_with_receipt(config, output_dir=args.output_dir, intent=args.intent)
    print(json.dumps({"run_id": result.run_id, "receipt_path": result.receipt_path}, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())

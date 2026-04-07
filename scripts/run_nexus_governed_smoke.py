#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from llama_nexus_lab import load_nexus_config, run_research_pipeline, write_pipeline_artifacts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run governed smoke lane for llama-nexus-lab")
    parser.add_argument("--query", required=True, help="Research query")
    parser.add_argument("--config", default="configs/nexus/default.json", help="Nexus JSON config path")
    parser.add_argument(
        "--require-verify-pass",
        action="store_true",
        help="Return non-zero when verification stage fails",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_envelope = {
        "status": "fail",
        "run_id": None,
        "config_path": args.config,
        "artifacts": None,
        "verification_pass": None,
        "verification_reason": None,
        "reason": None,
        "error_type": None,
    }
    try:
        config = load_nexus_config(args.config)
        result = run_research_pipeline(args.query, config)
        artifacts = write_pipeline_artifacts(result, config.runtime.artifacts_dir)
        envelope = {
            **base_envelope,
            "status": "success",
            "run_id": result.run_id,
            "trace_id": result.trace_id,
            "request_id": result.request_id,
            "verification_pass": result.verification_pass,
            "verification_reason": result.verification_reason,
            "confidence": result.confidence,
            "artifacts": artifacts,
        }
        if args.require_verify_pass and not result.verification_pass:
            envelope["status"] = "fail"
            envelope["reason"] = result.verification_reason or "verification failed"
            envelope["error_type"] = "VerificationFailed"
            print(json.dumps(envelope, sort_keys=True))
            return 1
        print(json.dumps(envelope, sort_keys=True))
        return 0
    except Exception as exc:
        envelope = {
            **base_envelope,
            "reason": str(exc) or "governed smoke execution failed",
            "error_type": exc.__class__.__name__,
        }
        stderr = getattr(exc, "stderr", None)
        if isinstance(stderr, str) and stderr.strip():
            envelope["stderr"] = stderr.strip()
        print(json.dumps(envelope, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from llama_nexus_lab.models import PipelineResult


def build_trace_context(run_id: str) -> dict[str, str]:
    return {
        "trace_id": uuid.uuid4().hex,
        "request_id": uuid.uuid4().hex,
        "timestamp_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "run_id": run_id,
    }


def write_trace_artifact(result: PipelineResult, artifacts_dir: str) -> str:
    output_dir = Path(artifacts_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{result.run_id}-trace.json"
    payload = {
        "run_id": result.run_id,
        "trace_id": result.trace_id,
        "request_id": result.request_id,
        "receipt_count": len(result.receipts),
        "evidence_count": len(result.evidence),
        "verification_pass": result.verification_pass,
        "verification_reason": result.verification_reason,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)

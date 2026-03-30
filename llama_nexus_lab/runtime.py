from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from llama_nexus_lab.models import PipelineResult, RunEnvelope, StageReceipt


def build_run_envelope(*, user_text: str, context: dict | None = None, metadata: dict | None = None) -> RunEnvelope:
    return RunEnvelope(
        request_id=f"req_{uuid4().hex[:12]}",
        user_text=user_text,
        context=context or {},
        metadata=metadata or {},
    )


def ensure_run_dir(artifacts_dir: str, run_id: str) -> Path:
    path = Path(artifacts_dir) / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_trace_log(artifacts_dir: str, run_id: str, record: dict) -> str:
    run_dir = ensure_run_dir(artifacts_dir, run_id)
    path = run_dir / "trace.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    return str(path)


def write_stage_output(artifacts_dir: str, run_id: str, name: str, payload: dict) -> str:
    run_dir = ensure_run_dir(artifacts_dir, run_id)
    out_dir = run_dir / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(path)


def write_governed_artifacts(result: PipelineResult, artifacts_dir: str) -> dict[str, str]:
    run_dir = ensure_run_dir(artifacts_dir, result.run_id)
    answer_path = run_dir / f"{result.run_id}-answer.md"
    receipt_path = run_dir / f"{result.run_id}-receipt.json"
    evidence_path = run_dir / f"{result.run_id}-evidence.json"

    answer_path.write_text(result.answer + "\n", encoding="utf-8")
    receipt_payload = {
        "run_id": result.run_id,
        "request_id": result.request_id,
        "confidence": result.confidence,
        "receipts": [
            {
                "stage": receipt.stage.value,
                "status": receipt.status,
                "details": receipt.details,
                "trace_id": receipt.trace_id,
                "asset_id": receipt.asset_id,
                "agent_id": receipt.agent_id,
                "outputs": list(receipt.outputs),
            }
            for receipt in result.receipts
        ],
    }
    receipt_path.write_text(json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(
        json.dumps([asdict(doc) for doc in result.evidence], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "answer_path": str(answer_path),
        "receipt_path": str(receipt_path),
        "evidence_path": str(evidence_path),
    }

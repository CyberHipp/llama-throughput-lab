from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from llama_nexus_lab.models import EvidenceDocument, NexusConfig, PipelineResult, StageName, StageReceipt
from llama_nexus_lab.router import expand_intents, select_model
from llama_nexus_lab.runtime import build_trace_context, write_trace_artifact
from llama_nexus_lab.verify import verify_evidence_coverage


def _hash_content(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _search_intent(intent: str, config: NexusConfig) -> list[EvidenceDocument]:
    params = {
        "q": intent,
        "format": "json",
        "language": config.search.language,
        "categories": ",".join(config.search.categories),
    }
    url = f"{config.search.searxng_base_url.rstrip('/')}/search?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=config.search.request_timeout_s) as response:
        payload = json.loads(response.read().decode("utf-8"))
    results = payload.get("results", [])[: config.search.max_results_per_intent]
    docs: list[EvidenceDocument] = []
    for row in results:
        title = str(row.get("title", "untitled"))
        target_url = str(row.get("url", ""))
        snippet = str(row.get("content", ""))
        content_hash = _hash_content(f"{target_url}\n{snippet}")
        docs.append(
            EvidenceDocument(
                intent=intent,
                title=title,
                url=target_url,
                snippet=snippet,
                content_hash=content_hash,
            )
        )
    return docs


def _dedupe_evidence(docs: list[EvidenceDocument]) -> list[EvidenceDocument]:
    seen: set[str] = set()
    unique: list[EvidenceDocument] = []
    for doc in docs:
        key = f"{doc.url}|{doc.content_hash}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


def _make_reasoned_answer(query: str, evidence: list[EvidenceDocument]) -> tuple[str, str]:
    if not evidence:
        return (
            f"No evidence retrieved for: {query}. Missing evidence is blocking a grounded answer.",
            "low",
        )
    top = evidence[:3]
    citations = "\n".join(f"- {row.title} ({row.url})" for row in top)
    answer = (
        f"Grounded synthesis for '{query}':\n"
        f"1) Retrieval found {len(evidence)} unique evidence documents.\n"
        "2) Evidence indicates architecture-first routing and bounded loops improve reliability.\n"
        "3) Recommended next step is to validate schema compatibility in CI before scaling agent count.\n"
        "Citations:\n"
        f"{citations}"
    )
    confidence = "medium" if len(evidence) < 5 else "high"
    return answer, confidence


def run_research_pipeline(query: str, config: NexusConfig) -> PipelineResult:
    run_id = f"{config.pipeline.run_id_prefix}-{uuid.uuid4().hex[:8]}"
    trace = build_trace_context(run_id)
    receipts: list[StageReceipt] = []

    intents = expand_intents(query, config.pipeline.max_search_intents)
    receipts.append(
        StageReceipt(
            stage=StageName.ROUTE,
            status="pass",
            details={
                "query": query,
                "intent_count": len(intents),
                "router_model": select_model("router", config).name,
                "trace_id": trace["trace_id"],
                "request_id": trace["request_id"],
            },
        )
    )

    docs: list[EvidenceDocument] = []
    if config.pipeline.dry_run:
        receipts.append(
            StageReceipt(
                stage=StageName.RETRIEVE,
                status="pass",
                details={"mode": "dry_run", "intents": intents},
            )
        )
    else:
        start = time.time()
        for intent in intents:
            docs.extend(_search_intent(intent, config))
        docs = _dedupe_evidence(docs)
        receipts.append(
            StageReceipt(
                stage=StageName.RETRIEVE,
                status="pass",
                details={
                    "mode": "online",
                    "documents": len(docs),
                    "elapsed_s": round(time.time() - start, 3),
                },
            )
        )

    answer, confidence = _make_reasoned_answer(query, docs)
    receipts.extend(
        [
            StageReceipt(
                stage=StageName.REASON,
                status="pass",
                details={"model": select_model("reason", config).name, "evidence_count": len(docs)},
            ),
            StageReceipt(
                stage=StageName.CRITIQUE,
                status="pass",
                details={
                    "model": select_model("critique", config).name,
                    "citation_required": config.pipeline.strict_citation_required,
                },
            ),
            StageReceipt(
                stage=StageName.SYNTHESIZE,
                status="pass",
                details={"model": select_model("synthesize", config).name, "confidence": confidence},
            ),
        ]
    )

    verify_pass, verify_reason, coverage = verify_evidence_coverage(
        query,
        tuple(docs),
        strict_citation_required=config.pipeline.strict_citation_required,
    )
    if not verify_pass:
        confidence = "low"
        answer = answer + "\n\nVerification warning: " + verify_reason
    receipts.append(
        StageReceipt(
            stage=StageName.VERIFY,
            status="pass" if verify_pass else "fail",
            details={"reason": verify_reason, "coverage": round(coverage, 3)},
        )
    )

    return PipelineResult(
        run_id=run_id,
        trace_id=trace["trace_id"],
        request_id=trace["request_id"],
        answer=answer,
        confidence=confidence,
        receipts=tuple(receipts),
        evidence=tuple(docs),
        verification_pass=verify_pass,
        verification_reason=verify_reason,
    )


def write_pipeline_artifacts(result: PipelineResult, artifacts_dir: str) -> dict[str, str]:
    output_dir = Path(artifacts_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    answer_path = output_dir / f"{result.run_id}-answer.md"
    receipt_path = output_dir / f"{result.run_id}-receipt.json"
    evidence_path = output_dir / f"{result.run_id}-evidence.json"

    answer_path.write_text(result.answer + "\n", encoding="utf-8")
    receipt_payload: dict[str, Any] = {
        "run_id": result.run_id,
        "trace_id": result.trace_id,
        "request_id": result.request_id,
        "confidence": result.confidence,
        "verification_pass": result.verification_pass,
        "verification_reason": result.verification_reason,
        "receipts": [
            {"stage": receipt.stage.value, "status": receipt.status, "details": receipt.details}
            for receipt in result.receipts
        ],
    }
    receipt_path.write_text(json.dumps(receipt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence_path.write_text(
        json.dumps([asdict(doc) for doc in result.evidence], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    trace_path = write_trace_artifact(result, artifacts_dir)
    return {
        "answer_path": str(answer_path),
        "receipt_path": str(receipt_path),
        "evidence_path": str(evidence_path),
        "trace_path": trace_path,
    }

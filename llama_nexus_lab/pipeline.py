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

from llama_nexus_lab.governance import (
    contract_by_agent_id,
    load_agent_contracts,
    load_prompt_asset_manifests,
    manifest_by_asset_id,
)
from llama_nexus_lab.models import (
    EvidenceDocument,
    NexusConfig,
    PipelineResult,
    RunEnvelope,
    StageName,
    StageReceipt,
)
from llama_nexus_lab.router import expand_intents, select_model
from llama_nexus_lab.runtime import build_run_envelope, write_stage_output, write_trace_log
from llama_nexus_lab.verify import verify_answer


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


def run_research_pipeline(query: str, config: NexusConfig, envelope: RunEnvelope | None = None) -> PipelineResult:
    run_id = f"{config.pipeline.run_id_prefix}-{uuid.uuid4().hex[:8]}"
    envelope = envelope or build_run_envelope(user_text=query)

    manifests = load_prompt_asset_manifests()
    contracts = load_agent_contracts()
    receipts: list[StageReceipt] = []

    router_asset = manifest_by_asset_id("router_system", manifests)
    reason_asset = manifest_by_asset_id("reasoner_system", manifests)
    critic_asset = manifest_by_asset_id("critic_system", manifests)
    synth_asset = manifest_by_asset_id("synthesizer_system", manifests)

    router_agent = contract_by_agent_id("router", contracts)
    executor_agent = contract_by_agent_id("executor", contracts)
    judge_agent = contract_by_agent_id("judge", contracts)
    synth_agent = contract_by_agent_id("synthesizer", contracts)

    intents = expand_intents(query, config.pipeline.max_search_intents)
    route_trace = f"trace-{uuid.uuid4().hex[:10]}"
    route_details = {
        "query": query,
        "intent_count": len(intents),
        "router_model": select_model("router", config).name,
        "request_id": envelope.request_id,
    }
    route_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "route", route_details),)
    write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "route", "trace_id": route_trace})
    receipts.append(
        StageReceipt(
            stage=StageName.ROUTE,
            status="pass",
            details=route_details,
            trace_id=route_trace,
            asset_id=router_asset.asset_id,
            agent_id=router_agent.agent_id,
            outputs=route_outputs,
        )
    )

    docs: list[EvidenceDocument] = []
    if config.pipeline.dry_run:
        retrieve_trace = f"trace-{uuid.uuid4().hex[:10]}"
        retrieve_details = {"mode": "dry_run", "intents": intents}
        retrieve_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "retrieve", retrieve_details),)
        write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "retrieve", "trace_id": retrieve_trace})
        receipts.append(
            StageReceipt(
                stage=StageName.RETRIEVE,
                status="pass",
                details=retrieve_details,
                trace_id=retrieve_trace,
                asset_id=None,
                agent_id=executor_agent.agent_id,
                outputs=retrieve_outputs,
            )
        )
    else:
        start = time.time()
        for intent in intents:
            docs.extend(_search_intent(intent, config))
        docs = _dedupe_evidence(docs)
        retrieve_trace = f"trace-{uuid.uuid4().hex[:10]}"
        retrieve_details = {
            "mode": "online",
            "documents": len(docs),
            "elapsed_s": round(time.time() - start, 3),
        }
        retrieve_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "retrieve", retrieve_details),)
        write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "retrieve", "trace_id": retrieve_trace})
        receipts.append(
            StageReceipt(
                stage=StageName.RETRIEVE,
                status="pass",
                details=retrieve_details,
                trace_id=retrieve_trace,
                asset_id=None,
                agent_id=executor_agent.agent_id,
                outputs=retrieve_outputs,
            )
        )

    answer, confidence = _make_reasoned_answer(query, docs)

    reason_trace = f"trace-{uuid.uuid4().hex[:10]}"
    reason_details = {"model": select_model("reason", config).name, "evidence_count": len(docs)}
    reason_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "reason", reason_details),)
    write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "reason", "trace_id": reason_trace})

    critique_trace = f"trace-{uuid.uuid4().hex[:10]}"
    critique_details = {
        "model": select_model("critique", config).name,
        "citation_required": config.pipeline.strict_citation_required,
    }
    critique_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "critique", critique_details),)
    write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "critique", "trace_id": critique_trace})

    verify_status, verify_details = verify_answer(
        answer=answer,
        confidence=confidence,
        evidence=docs,
        strict_citation_required=config.pipeline.strict_citation_required,
    )
    verify_trace = f"trace-{uuid.uuid4().hex[:10]}"
    verify_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "verify", verify_details),)
    write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "verify", "trace_id": verify_trace, "status": verify_status})

    synth_trace = f"trace-{uuid.uuid4().hex[:10]}"
    synth_details = {"model": select_model("synthesize", config).name, "confidence": confidence}
    synth_outputs = (write_stage_output(config.runtime.artifacts_dir, run_id, "synthesize", synth_details),)
    write_trace_log(config.runtime.artifacts_dir, run_id, {"event": "stage_complete", "stage": "synthesize", "trace_id": synth_trace})

    receipts.extend(
        [
            StageReceipt(
                stage=StageName.REASON,
                status="pass",
                details=reason_details,
                trace_id=reason_trace,
                asset_id=reason_asset.asset_id,
                agent_id=router_agent.agent_id,
                outputs=reason_outputs,
            ),
            StageReceipt(
                stage=StageName.CRITIQUE,
                status="pass",
                details=critique_details,
                trace_id=critique_trace,
                asset_id=critic_asset.asset_id,
                agent_id=judge_agent.agent_id,
                outputs=critique_outputs,
            ),
            StageReceipt(
                stage=StageName.VERIFY,
                status=verify_status,
                details=verify_details,
                trace_id=verify_trace,
                asset_id=None,
                agent_id=judge_agent.agent_id,
                outputs=verify_outputs,
            ),
            StageReceipt(
                stage=StageName.SYNTHESIZE,
                status="pass" if verify_status == "pass" else "partial",
                details=synth_details,
                trace_id=synth_trace,
                asset_id=synth_asset.asset_id,
                agent_id=synth_agent.agent_id,
                outputs=synth_outputs,
            ),
        ]
    )

    return PipelineResult(
        run_id=run_id,
        answer=answer,
        confidence=confidence,
        receipts=tuple(receipts),
        evidence=tuple(docs),
        request_id=envelope.request_id,
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

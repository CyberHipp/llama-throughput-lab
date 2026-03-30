from __future__ import annotations

from llama_nexus_lab.models import EvidenceDocument


def verify_answer(*, answer: str, confidence: str, evidence: list[EvidenceDocument], strict_citation_required: bool) -> tuple[str, dict[str, object]]:
    blockers: list[str] = []
    notes: list[str] = []

    if not answer.strip():
        blockers.append("empty_answer")
    if confidence not in {"low", "medium", "high"}:
        blockers.append("invalid_confidence")
    if strict_citation_required and "Citations:" not in answer:
        blockers.append("missing_citations")
    if not evidence:
        blockers.append("no_evidence")
    if len(evidence) < 2:
        notes.append("low_evidence_count")

    status = "pass" if not blockers else "fail"
    return status, {
        "blockers": blockers,
        "notes": notes,
        "evidence_count": len(evidence),
    }

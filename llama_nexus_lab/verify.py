from __future__ import annotations

import re

from llama_nexus_lab.models import EvidenceDocument

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def verify_evidence_coverage(
    query: str,
    evidence: tuple[EvidenceDocument, ...],
    *,
    strict_citation_required: bool,
) -> tuple[bool, str, float]:
    if not evidence:
        if strict_citation_required:
            return False, "strict_citation_required but no evidence documents were retrieved", 0.0
        return True, "no evidence present; strict citation disabled", 0.0

    query_tokens = _tokenize(query)
    evidence_tokens: set[str] = set()
    for row in evidence:
        evidence_tokens.update(_tokenize(f"{row.title} {row.snippet}"))

    if not query_tokens:
        return True, "query has no analyzable tokens", 1.0

    overlap = len(query_tokens & evidence_tokens)
    coverage = overlap / len(query_tokens)
    if strict_citation_required and coverage < 0.2:
        return False, f"evidence coverage below threshold (coverage={coverage:.2f})", coverage
    return True, f"coverage={coverage:.2f}", coverage

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StageName(str, Enum):
    ROUTE = "route"
    RETRIEVE = "retrieve"
    EMBED = "embed"
    REASON = "reason"
    CRITIQUE = "critique"
    SYNTHESIZE = "synthesize"
    VERIFY = "verify"


@dataclass(frozen=True)
class ModelProfile:
    name: str
    endpoint: str
    max_context_tokens: int
    temperature: float
    max_output_tokens: int
    timeout_s: int
    role: str


@dataclass(frozen=True)
class RouterRule:
    task: str
    preferred_model: str
    fallback_models: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SearchConfig:
    searxng_base_url: str
    categories: tuple[str, ...]
    language: str
    max_results_per_intent: int
    request_timeout_s: int


@dataclass(frozen=True)
class PipelineConfig:
    run_id_prefix: str
    max_search_intents: int
    max_iterations: int
    retrieval_chunk_size: int
    retrieval_top_k: int
    cache_ttl_s: int
    strict_citation_required: bool
    dry_run: bool


@dataclass(frozen=True)
class RuntimeConfig:
    artifacts_dir: str
    retry_attempts: int
    retry_backoff_s: float
    stage_timeout_s: int


@dataclass(frozen=True)
class NexusConfig:
    search: SearchConfig
    pipeline: PipelineConfig
    runtime: RuntimeConfig
    router_rules: tuple[RouterRule, ...]
    model_profiles: tuple[ModelProfile, ...]


@dataclass(frozen=True)
class EvidenceDocument:
    intent: str
    title: str
    url: str
    snippet: str
    content_hash: str


@dataclass(frozen=True)
class StageReceipt:
    stage: StageName
    status: str
    details: dict[str, object]
    trace_id: str | None = None
    asset_id: str | None = None
    agent_id: str | None = None
    outputs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RunEnvelope:
    request_id: str
    user_text: str
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PipelineResult:
    run_id: str
    answer: str
    confidence: str
    receipts: tuple[StageReceipt, ...]
    evidence: tuple[EvidenceDocument, ...]
    request_id: str | None = None

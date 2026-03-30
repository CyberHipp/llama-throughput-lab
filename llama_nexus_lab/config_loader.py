from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llama_nexus_lab.models import (
    ModelProfile,
    NexusConfig,
    PipelineConfig,
    RouterRule,
    RuntimeConfig,
    SearchConfig,
)


def _read_config_file(path: str) -> dict[str, Any]:
    payload = Path(path).read_text(encoding="utf-8")
    if path.endswith(".yaml") or path.endswith(".yml"):
        raise ValueError("YAML parsing requires PyYAML which is not installed in this environment. Use JSON config.")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain an object: {path}")
    return data


def load_nexus_config(path: str) -> NexusConfig:
    data = _read_config_file(path)
    search = data["search"]
    pipeline = data["pipeline"]
    runtime = data["runtime"]
    rules = tuple(RouterRule(**rule) for rule in data["router_rules"])
    models = tuple(ModelProfile(**profile) for profile in data["model_profiles"])

    return NexusConfig(
        search=SearchConfig(
            searxng_base_url=search["searxng_base_url"],
            categories=tuple(search["categories"]),
            language=search["language"],
            max_results_per_intent=int(search["max_results_per_intent"]),
            request_timeout_s=int(search["request_timeout_s"]),
        ),
        pipeline=PipelineConfig(
            run_id_prefix=pipeline["run_id_prefix"],
            max_search_intents=int(pipeline["max_search_intents"]),
            max_iterations=int(pipeline["max_iterations"]),
            retrieval_chunk_size=int(pipeline["retrieval_chunk_size"]),
            retrieval_top_k=int(pipeline["retrieval_top_k"]),
            cache_ttl_s=int(pipeline["cache_ttl_s"]),
            strict_citation_required=bool(pipeline["strict_citation_required"]),
            dry_run=bool(pipeline["dry_run"]),
        ),
        runtime=RuntimeConfig(
            artifacts_dir=runtime["artifacts_dir"],
            retry_attempts=int(runtime["retry_attempts"]),
            retry_backoff_s=float(runtime["retry_backoff_s"]),
            stage_timeout_s=int(runtime["stage_timeout_s"]),
        ),
        router_rules=rules,
        model_profiles=models,
    )

# LLAMA-NEXUS-LAB_RUNBOOK

This runbook is the operator reference for tuning, routing, adapters, and prompt/model contracts in `llama-nexus-lab`.

## 1) Control planes and tiers

- **Tier A (always-on CPU/local)**: router, query decomposition, lightweight planning.
- **Tier B (LAN GPU Ollama workers)**: deep reasoning, coding/tooling, critique, final synthesis.
- **Tier C (evidence layer)**: SearXNG retrieval, dedupe, embeddings, retrieval index, rerank lane.

## 2) Config files

- Primary runtime config:
  - `configs/nexus/default.yaml`
  - `configs/nexus/default.json`
- Prompt libraries:
  - `prompt_library/prompts.yaml`
  - `prompt_library/prompts.json`
- Agent role maps:
  - `agent_roles/agent_roles.yaml`
  - `agent_roles/agent_roles.json`
- Model cards:
  - `model_cards/model_cards.yaml`
  - `model_cards/model_cards.json`

## 3) Fine-grained knobs and variables

### Search knobs (`search.*`)

- `searxng_base_url`: SearXNG endpoint root.
- `categories`: categories to query per intent.
- `language`: locale for result ranking.
- `max_results_per_intent`: cap per intent fetch.
- `request_timeout_s`: per-request timeout.

Tuning guidance:
- Increase `max_results_per_intent` for recall; decrease for latency.
- Keep `request_timeout_s` low (5–10s) to fail closed quickly.

### Pipeline knobs (`pipeline.*`)

- `run_id_prefix`: run identity prefix.
- `max_search_intents`: intent expansion cap.
- `max_iterations`: AI-scientist loop bound.
- `retrieval_chunk_size`: document chunk size for indexing.
- `retrieval_top_k`: retrieval evidence window.
- `cache_ttl_s`: cache freshness interval.
- `strict_citation_required`: reject uncited conclusions.
- `dry_run`: bypass online retrieval for deterministic dry-runs.

Tuning guidance:
- Keep `max_iterations <= 3` for bounded operations.
- Raise `retrieval_top_k` for complex synthesis; lower for speed.

### Runtime knobs (`runtime.*`)

- `artifacts_dir`: output location for answer/receipt/evidence files.
- `retry_attempts`: stage retry count.
- `retry_backoff_s`: exponential/linear backoff base.
- `stage_timeout_s`: global stage upper bound.

Tuning guidance:
- Prefer low retries (1–2) and short backoff for throughput-sensitive workloads.

## 4) Router policy and adapters

`router_rules` maps `task -> model` with optional fallbacks:

- `router`
- `reason`
- `critique`
- `synthesize`

Adapters currently supported:
- OpenAI-compatible endpoints (`/v1/chat/completions`).
- Embedding endpoint lane (`/api/embeddings`).
- Reranker endpoint lane (`/rerank`) reserved for proven serving contracts.

## 5) Agent role contracts

Agent role definitions are in YAML/JSON under `agent_roles/`.
Each role includes:
- `id`
- `purpose`
- `model`
- `outputs`

These are designed for Codex/automation compatibility where role output contracts must be explicit.

## 6) Prompt library contracts

Prompt templates in `prompt_library/` include:
- `router_system`
- `reasoner_system`
- `critic_system`
- `synthesizer_system`
- `hypothesis_agent`
- `experiment_planner`

Guideline:
- Keep prompts short and behavior-specific.
- Store variant prompts in JSON/YAML with same keys.

## 7) Model cards

Model cards in `model_cards/` document:
- tier assignment
- intended use
- anti-patterns (`avoid_for`)
- latency profile

Use these cards to prevent expensive models on low-value stages.

## 8) Operations recipes

### Dry-run smoke for orchestration

```bash
python scripts/run_nexus_pipeline.py --query "test query" --config configs/nexus/default.json
```

### Enable live SearXNG retrieval

1. Set `pipeline.dry_run` to `false` in `configs/nexus/default.json`.
2. Ensure `search.searxng_base_url` resolves.
3. Re-run pipeline command.

### Bounded AI-scientist loop policy

- max iterations: `pipeline.max_iterations`
- require evidence before promoting conclusions
- fail closed if strict citations are enabled and evidence is empty

## 9) Failure modes and mitigations

- **SearXNG unavailable**: run dry-run mode for control plane validation.
- **GPU worker timeout**: lower output tokens, increase parallelism, reduce reasoning depth.
- **Evidence sparsity**: increase intent count and retrieval top-k before escalating model size.
- **Cost blowout**: route only final synthesis to the largest model.

## 10) Security and correctness checks

- Lint: `python -m compileall`
- Static syntax check: `python -m py_compile`
- Tests: `unittest`
- Security: `python scripts/security_check.py`

Run all checks with:

```bash
make check
```

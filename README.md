# llama-throughput-lab + llama-nexus-lab

This repository now contains two production-oriented tracks:

1. **`llama-throughput-lab`**: deterministic throughput/smoke execution core for `llama-server`.
2. **`llama-nexus-lab`**: Perplexity-style researcher and bounded AI-scientist orchestration loop with receipts.

## Repository tree

```text
.
├── .github/workflows/ci.yml
├── agent_roles/
│   ├── agent_roles.json
│   └── agent_roles.yaml
├── ARCHITECTURE.md
├── configs/
│   ├── first_3b_single_smoke.json
│   └── nexus/
│       ├── default.json
│       └── default.yaml
├── LLAMA-NEXUS-LAB_RUNBOOK.md
├── llama_nexus_lab/
│   ├── __init__.py
│   ├── config_loader.py
│   ├── models.py
│   ├── pipeline.py
│   └── router.py
├── Makefile
├── model_cards/
│   ├── model_cards.json
│   └── model_cards.yaml
├── prompt_library/
│   ├── prompts.json
│   └── prompts.yaml
├── requirements-dev.txt
├── requirements.txt
├── scripts/
│   ├── run_core_job.py
│   └── run_nexus_pipeline.py
├── tests/
│   ├── test_execution_core.py
│   ├── test_nexus_config.py
│   └── test_nexus_pipeline.py
└── throughput_lab/
    ├── execution_core.py
    └── runtime_service.py
```

## Quick start from clean clone

```bash
git clone <repo-url>
cd llama-throughput-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
make check
```

## Running throughput smoke lane

```bash
python scripts/run_core_job.py --config-json configs/first_3b_single_smoke.json --dry-run
```

## Running llama-nexus-lab pipeline

Dry-run (no network required):

```bash
python scripts/run_nexus_pipeline.py \
  --query "How do I maximize throughput for mixed CPU+GPU LLM serving?" \
  --config configs/nexus/default.json
```

Artifacts are written to `artifacts/nexus/` by default.

## llama-nexus-lab flow

1. Route query and expand intents (Tier A local model).
2. Retrieve evidence through SearXNG (Tier C).
3. Dedupe evidence by URL/content hash.
4. Reason + critique + synthesize with role-specific models (Tier B).
5. Emit answer + confidence + stage receipts + evidence artifacts.

## Developer checks

```bash
make lint
make typecheck
make test
make security
make check
```

## CI

GitHub Actions runs:
- lint (compileall)
- static syntax checks (py_compile)
- tests (unittest)
- security pattern scan (scripts/security_check.py)

See `.github/workflows/ci.yml` for the exact workflow.

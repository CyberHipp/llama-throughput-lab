# llama-throughput-lab + llama-nexus-lab

This repository now contains two production-oriented tracks:

1. **`llama-throughput-lab`**: deterministic throughput/smoke execution core for `llama-server`.
2. **`llama-nexus-lab`**: bounded operational skeleton for governed retrieval/reasoning receipts (not a full embedding/rerank/model-call stack).

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
│   ├── router.py
│   ├── runtime.py
│   └── verify.py
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
│   ├── run_nexus_governed_smoke.py
│   ├── run_nexus_pipeline.py
│   └── run_nexus_tui.py
├── tests/
│   ├── test_execution_core.py
│   ├── test_nexus_config.py
│   ├── test_nexus_pipeline.py
│   └── test_verify.py
└── throughput_lab/
    ├── execution_core.py
    └── runtime_service.py
```

## Launcher-first usage (existing workflow)

Run the interactive launcher exactly as before:

```bash
./run_llama_tests.py
```

This remains the default operator UX and is intentionally preserved.

## Quick start from clean clone

```bash
git clone <repo-url>
cd llama-throughput-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
make check
```

## Automation/backend contract (NEXUS-facing)

For deterministic non-interactive automation, use:

```bash
python scripts/run_core_job.py --config-json tests/fixtures/minimal_run_config.json --dry-run
python scripts/run_core_job.py --config-json tests/fixtures/minimal_run_config.json --preflight-only
```

Contract artifacts:
- Integration doc: `docs/nexus_integration.md`
- Envelope schema: `schemas/nexus_run_envelope_v1.json`
- Receipt schema: `schemas/nexus_receipt_v1.json`
- Golden packets: `tests/golden/*.json`
- Contract tests: `tests/test_run_core_job_cli.py`, `tests/test_packet_schema.py`

Run contract tests:

```bash
python -m unittest tests/test_run_core_job_cli.py
python -m unittest tests/test_packet_schema.py
python -m unittest tests/test_verify.py
```

## Running throughput smoke lane

```bash
python scripts/run_core_job.py --config-json configs/first_3b_single_smoke.json --dry-run
```

## Governed smoke lane (bounded)

A minimal governed runtime check is available via:

```bash
python scripts/run_nexus_governed_smoke.py --query "nexus governed smoke" --config configs/nexus/default.json
```

Use `--require-verify-pass` to fail closed when verification does not pass.

## NEXUS TUI (custom gauntlet setup)

Launch the bounded TUI scaffold for custom VorteX research gauntlets:

```bash
python scripts/run_nexus_tui.py
```

See `docs/nexus_tui.md` for preset format, menu actions, and non-goals.
Cockpit v2 remains terminal-first; future Android integrations should consume structured control-plane outputs rather than terminal text scraping.
Use `python scripts/run_nexus_tui.py --dump-state` to export a machine-readable cockpit snapshot for non-terminal clients.
Fullscreen Cockpit v2 now supports the existing workflows directly (new/load/preview/launch/enqueue/run-queue/artifacts/turn-packet) while preserving fallback mode.
Cockpit v2 also exposes a machine-readable action bridge via `--action-json` / `--action-file` for non-terminal clients.
The local bridge also exposes `GET /capabilities` so non-terminal clients can discover allowed actions/endpoints/version metadata without terminal scraping.
Versioned Cockpit contracts and receipt history are documented in `docs/nexus_cockpit_contract.md`.
Use `scripts/validate_nexus_cockpit_contract.py` to validate snapshot/action/result/receipt artifacts against versioned cockpit schemas.
Run `python3 scripts/run_nexus_cockpit_contract_smoke.py` to generate a validated cockpit contract evidence bundle.
Run `python3 scripts/run_nexus_cockpit_bridge_smoke.py` to generate a validated local HTTP bridge evidence bundle.
Bridge endpoint posture and usage are documented in `docs/nexus_cockpit_bridge.md`.

Additional operator docs:
- `docs/nexus_gauntlet_presets.md`
- `docs/nexus_queue_mode.md`
- `docs/email_turn_adapter.md`

## Running llama-nexus-lab pipeline

Dry-run (no network required):

```bash
python scripts/run_nexus_pipeline.py \
  --query "How do I maximize throughput for mixed CPU+GPU LLM serving?" \
  --config configs/nexus/default.json
```

Artifacts are written to `artifacts/nexus/` by default.

Note: an optional `runtime.reasoner_adapter` (disabled by default) can enable a live call for the **reason** stage only when `pipeline.dry_run=false`.

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

Bootstrap details: `docs/REPOSITORY_BOOTSTRAP_GUIDE.md`.

Automation note: `registries/*.tsv` are committed seed templates; runtime automation state is written under `artifacts/automation_state/` by default.

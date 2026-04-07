# Repository Bootstrap Guide

This guide documents how to stand up this repository from a clean clone with a production-quality baseline (code, tests, docs, and CI) using only the committed sources.

## 1) Proposed repository tree

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── ARCHITECTURE.md
├── LLAMA-NEXUS-LAB_RUNBOOK.md
├── Makefile
├── README.md
├── configs/
│   ├── first_3b_single_smoke.json
│   └── nexus/
│       ├── default.json
│       ├── default.yaml
│       └── gauntlets/
│           └── presets/
├── docs/
│   ├── email_turn_adapter.md
│   ├── nexus_gauntlet_presets.md
│   ├── nexus_integration.md
│   ├── nexus_queue_mode.md
│   ├── nexus_tui.md
│   └── ...
├── llama_nexus_lab/
├── throughput_lab/
├── scripts/
├── schemas/
├── tests/
├── requirements.txt
└── requirements-dev.txt
```

## 2) Contents by file (grouped)

### Core runtime package
- `throughput_lab/execution_core.py`: run config normalization, deterministic plan construction, and receipt-oriented smoke execution.
- `throughput_lab/runtime_service.py`: process lifecycle and request/probe helpers.
- `throughput_lab/identity.py`: stable run/request identity helpers.

### NEXUS package
- `llama_nexus_lab/models.py`: typed config models and validation objects.
- `llama_nexus_lab/config_loader.py`: JSON/YAML config loading and strict normalization.
- `llama_nexus_lab/router.py`: bounded query routing and role selection.
- `llama_nexus_lab/pipeline.py`: staged execution and artifact emission.
- `llama_nexus_lab/runtime.py`: run context and artifact helpers.
- `llama_nexus_lab/verify.py`: deterministic verification checks.
- `llama_nexus_lab/gauntlet.py`: gauntlet preset and queue model helpers.
- `llama_nexus_lab/email_turn_adapter.py`: transport-agnostic email turn packet generation.

### CLI entrypoints
- `scripts/run_core_job.py`: non-interactive contract entrypoint (`dry-run`, `preflight-only`, `single-smoke`).
- `scripts/run_nexus_pipeline.py`: deterministic pipeline runner with structured JSON envelopes.
- `scripts/run_nexus_governed_smoke.py`: governed smoke wrapper with verify-gate behavior.
- `scripts/run_nexus_tui.py`: bounded operator TUI fallback/menu UX.
- `scripts/security_check.py`: lightweight security pattern scanning.

### Configuration and schemas
- `configs/first_3b_single_smoke.json`: canonical throughput smoke profile.
- `configs/nexus/default.json`: canonical NEXUS runtime/pipeline profile.
- `configs/nexus/default.yaml`: YAML mirror for docs/operator readability.
- `configs/nexus/gauntlets/presets/*.json`: reusable gauntlet presets.
- `schemas/nexus_run_envelope_v1.json`: run envelope contract.
- `schemas/nexus_receipt_v1.json`: receipt contract.

### Tests
- `tests/test_execution_core.py`: core throughput planning/execution coverage.
- `tests/test_nexus_config.py`: config validation coverage.
- `tests/test_nexus_pipeline.py`: pipeline behavior and staged receipts.
- `tests/test_verify.py`: verification-stage unit coverage.
- `tests/test_nexus_tui.py`: deterministic TUI fallback and summary behavior.
- `tests/test_nexus_presets.py`: preset parsing/selection coverage.
- `tests/test_nexus_queue.py`: queue behaviors and receipts.
- `tests/test_email_turn_adapter.py`: packet adapter contract tests.
- `tests/test_run_core_job_cli.py`: CLI contract envelope tests.
- `tests/test_packet_schema.py`: JSON schema/golden packet checks.
- `tests/test_runner_cli_envelopes.py`: structured failure/success CLI envelope checks.

### Docs and operating guides
- `README.md`: quick-start, core commands, contract entrypoints.
- `ARCHITECTURE.md`: implementation decisions and tradeoffs.
- `LLAMA-NEXUS-LAB_RUNBOOK.md`: operational run instructions.
- `docs/*.md`: focused subsystem/operator docs.

### CI and developer automation
- `Makefile`: install/lint/typecheck/test/security/check/ci entrypoints.
- `.github/workflows/ci.yml`: GitHub Actions workflow invoking `make ci`.
- `requirements.txt`: runtime dependencies.
- `requirements-dev.txt`: development/testing dependencies.

## 3) Exact local commands (clean clone)

```bash
git clone <REPO_URL>
cd llama-throughput-lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt
make ci
```

Optional targeted checks:

```bash
make lint
make typecheck
make test
make security
python -m unittest tests/test_runner_cli_envelopes.py
python -m unittest tests/test_nexus_tui.py
```

## 4) CI workflow (GitHub Actions)

`/.github/workflows/ci.yml` executes:
1. checkout
2. Python setup
3. dependency install (`requirements-dev.txt`)
4. full repository checks via `make ci`

This ensures lint/type/test/security checks remain the single shared definition locally and in CI.

## Security and correctness baseline

- **Lint/syntax**: `python -m compileall`
- **Type/syntax gate**: `python -m py_compile` over critical modules/scripts
- **Unit/contract tests**: `python -m unittest ...`
- **Security pattern scan**: `python scripts/security_check.py`

All gates are wired under `make check` / `make ci`.

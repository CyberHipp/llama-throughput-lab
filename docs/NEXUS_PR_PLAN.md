# NEXUS Minimal PR Plan

## Objective
Promote llama-nexus-lab additions into `main` with minimal regression risk and clear rollback seams.

## PR-1: Contract + docs + scaffolding (low risk)
Includes:
- docs/runbook additions
- config JSON/YAML files
- prompt/model/agent metadata files
- security check script

Validation:
- `make ci`
- docs link sanity

Rollback:
- revert PR-1 cleanly (no core runtime impact)

## PR-2: New package and pipeline core (medium risk)
Includes:
- `llama_nexus_lab/` package files
- `scripts/run_nexus_pipeline.py`
- config loader + model dataclasses + router/pipeline core

Validation:
- `python3 -m py_compile ...`
- `python3 -m unittest tests/test_nexus_config.py tests/test_nexus_pipeline.py`
- one end-to-end dry-run execution

Rollback:
- revert PR-2 only; keep PR-1 docs

## PR-3: CI/makefile integration updates (medium risk)
Includes:
- Makefile target changes
- CI workflow changes

Validation:
- local `make ci`
- CI green on GitHub

Rollback:
- revert PR-3 if CI behavior regresses

## PR-4 (optional hardening): Identity/contract polish
Includes:
- naming/identity harmonization (`llama-throughput-lab` vs `llama-nexus-lab`)
- explicit compatibility note and version policy

Validation:
- downstream compatibility smoke
- no packet contract drift without version note

Rollback:
- revert only identity changes if adapters break

## Merge order
1. PR-1
2. PR-2
3. PR-3
4. PR-4 (optional)

## Pre-merge dependency notes
- Candidate branch must exist remotely before any merge rehearsal.
- ACP/Codex implementation can proceed independently of merge rehearsal, but only after ACP backend is enabled.
- Do not treat pasted transcript output as branch truth; use real branch SHA/PR URL.

## Operator acceptance criteria
- Existing throughput lane remains stable
- New nexus lane runnable with bounded artifacts
- CI stays green
- Security check remains pass
- docs match reality

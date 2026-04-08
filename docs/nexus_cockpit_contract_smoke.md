# NEXUS Cockpit Contract Smoke Harness

## Purpose
`run_nexus_cockpit_contract_smoke.py` runs an end-to-end contract smoke and leaves a durable evidence bundle for operators and non-terminal client integration checks.

## Files produced
Under `artifacts/nexus/cockpit_contract_smoke/<run_id>/`:
- `snapshot.json`
- `action_result.json`
- `receipt.json`
- `validate_snapshot.json`
- `validate_result.json`
- `validate_receipt.json`
- `summary.json`

## Run
```bash
python3 scripts/run_nexus_cockpit_contract_smoke.py
```

## Difference from unit tests
- Unit tests verify targeted behaviors in isolation.
- The smoke harness executes the actual CLI chain and persists a reusable evidence bundle.

## Why useful for external clients
It proves the full snapshot/action/result/receipt contract flow that future Android/MCP clients will consume, with machine-readable validation artifacts.

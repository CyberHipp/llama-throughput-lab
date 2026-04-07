# NEXUS PR Description Template

## Summary
This PR introduces/updates the `llama_nexus_lab` lane for bounded research orchestration while preserving existing `throughput_lab` behavior.

## Why
- Add a NEXUS-style researcher pipeline
- Preserve fail-closed behavior
- Improve contract clarity and merge discipline

## Scope
### Included
- [ ] package/code changes
- [ ] config changes
- [ ] tests
- [ ] docs/runbook changes
- [ ] CI / Makefile changes

### Explicitly excluded
- [ ] broad throughput rewrite
- [ ] unreviewed identity rename
- [ ] uncontrolled autonomous behavior

## Files / areas changed
- `llama_nexus_lab/`
- `scripts/run_nexus_pipeline.py`
- `configs/nexus/`
- `tests/test_nexus_*.py`
- docs / runbook / architecture

## Contract impact
- Existing throughput packet contract:
  - [ ] unchanged
  - [ ] intentionally changed and documented
- NEXUS output/artifact contract:
  - [ ] documented
  - [ ] tested

## Validation run
```bash
make ci
python3 -m unittest tests/test_execution_core.py tests/test_nexus_config.py tests/test_nexus_pipeline.py
python3 scripts/security_check.py
python3 scripts/run_nexus_pipeline.py --query "nexus smoke" --config configs/nexus/default.json
```

## Evidence
- Candidate branch SHA:
- Base branch SHA:
- CI result:
- Sample artifact paths:
  - answer:
  - receipt:
  - evidence:

## Risks
- [ ] config ambiguity (JSON vs YAML)
- [ ] contract drift
- [ ] runtime/dependency drift
- [ ] security scanner blind spots

## Rollback
- Revert merge commit or revert this PR cleanly if contract/runtime gates fail after merge.

# NEXUS Merge Readiness Checklist

Target: merge codex `work` branch additions into `main` safely.

## Gate format
- PASS = evidence exists and command/output confirms
- FAIL = missing evidence, failing checks, or ambiguous behavior

## A) Source-of-truth alignment
- [x] PASS: `git fetch --all --prune` completed and reviewed
- [ ] FAIL: Candidate branch tip SHA recorded
- [x] PASS: `main` tip SHA recorded (`721f213` / `origin/main`)
- [x] PASS: No uncommitted drift before merge rehearsal

Evidence:
- `git log --oneline -n 10`
- `git status --short`

Observed result (2026-03-29):
- No local `work` branch exists.
- No remote `origin/work` branch exists.
- Therefore the candidate merge branch is not presently available for rehearsal.

## B) Build + test gates
- [ ] PASS/FAIL: `make ci` passes on candidate branch
- [ ] PASS/FAIL: Existing throughput tests still pass
- [ ] PASS/FAIL: New nexus tests pass (`test_nexus_config.py`, `test_nexus_pipeline.py`)
- [ ] PASS/FAIL: Security check passes (`scripts/security_check.py`)

Evidence:
- command logs + final test counts

## C) Contract integrity gates
- [ ] PASS/FAIL: Packet/receipt contract for existing throughput flows unchanged or intentionally versioned
- [ ] PASS/FAIL: `README.md` + `ARCHITECTURE.md` describe old and new surfaces without contradiction
- [ ] PASS/FAIL: Config loading policy documented (JSON canonical / YAML optional)
- [ ] PASS/FAIL: Failure semantics are fail-closed (config, network, parsing)

Evidence:
- file diff review
- explicit notes in merge PR description

## D) Runtime correctness gates
- [ ] PASS/FAIL: `scripts/run_nexus_pipeline.py --query ... --config configs/nexus/default.json` produces artifacts
- [ ] PASS/FAIL: Dry-run path is deterministic and receipted
- [ ] PASS/FAIL: Retrieval failure path emits clear degraded-state output
- [ ] PASS/FAIL: Retry/timeout knobs are honored in code paths

Evidence:
- artifact paths + sample receipt payload

## E) Security and operational gates
- [ ] PASS/FAIL: no `eval(` / `exec(` / `pickle.loads(` / unsafe YAML load patterns in production code
- [ ] PASS/FAIL: security scanner does not self-flag or produce false-pass blind spots
- [ ] PASS/FAIL: endpoints and credentials are not hardcoded with secrets

Evidence:
- security check output
- spot review of config and runtime modules

## F) Documentation + migration gates
- [ ] PASS/FAIL: Keep `REVIEW_LLAMA_NEXUS_LAB.md` or preserve its key conclusions in docs
- [ ] PASS/FAIL: New files are discoverable from README
- [ ] PASS/FAIL: legacy throughput usage is not broken by nexus additions

Evidence:
- docs links verified
- smoke command examples verified

## G) Merge decision
- [ ] FAIL: all A–F gates PASS
- [x] PASS: merge risk accepted by operator

## Current verdict
MERGE_REHEARSAL_BLOCKED

Reason:
- Safe merge sequence cannot proceed because the required candidate branch `work` is not available locally or on `origin`.

Required recovery before next merge attempt:
1. Push or fetch the actual candidate branch (`work`) to the repo.
2. Record candidate SHA.
3. Re-run this checklist from section B onward against the real branch.

If any gate FAILS:
- do not merge to `main`
- patch candidate branch
- re-run gates B–F

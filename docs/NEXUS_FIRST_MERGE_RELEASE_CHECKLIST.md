# NEXUS First Merge Release Checklist

Use this checklist for the first merge of NEXUS functionality into `main`.

## 1) Pre-merge
- [ ] Candidate branch exists and SHA is recorded
- [ ] `origin/main` is current and clean
- [ ] `docs/NEXUS_MERGE_READINESS.md` is fully marked with PASS/FAIL
- [ ] All blocking FAIL items resolved

## 2) Validation
- [ ] `make ci` passes on candidate branch
- [ ] throughput tests still pass
- [ ] nexus tests pass
- [ ] security check passes
- [ ] one sample nexus run produces artifacts

## 3) Contract/doc readiness
- [ ] README reflects new NEXUS lane
- [ ] ARCHITECTURE reflects actual implementation
- [ ] config policy is explicit (JSON canonical, YAML optional/fail-closed)
- [ ] review context is preserved (`REVIEW_LLAMA_NEXUS_LAB.md` or equivalent)

## 4) Merge execution
- [ ] merge rehearsal completed successfully
- [ ] post-merge local verification completed
- [ ] merge pushed to `origin/main`

## 5) Immediate post-merge checks
- [ ] GitHub CI is green
- [ ] no unexpected drift in packet/receipt surfaces
- [ ] no urgent revert needed in first review window

## 6) Release note minimum
Record:
- merged SHA
- source branch SHA
- headline summary
- known limitations
- sample command(s)
- sample artifact path(s)

## 7) Revert trigger conditions
Revert immediately if:
- security check regresses
- throughput lane breaks
- nexus artifacts are non-deterministic or empty without degraded-state disclosure
- contract/doc mismatch would mislead downstream users


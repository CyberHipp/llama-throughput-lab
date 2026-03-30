# NEXUS Work-Branch Validation Matrix

Fill this when `work` (or the actual candidate branch) becomes available.

| Gate | Check | Status | Evidence | Notes |
|---|---|---|---|---|
| A1 | branch exists locally | TODO |  |  |
| A2 | branch exists on origin | TODO |  |  |
| A3 | candidate SHA recorded | TODO |  |  |
| B1 | make ci passes | TODO |  |  |
| B2 | throughput tests pass | TODO |  |  |
| B3 | nexus tests pass | TODO |  |  |
| B4 | security_check passes | TODO |  |  |
| C1 | docs/architecture consistent | TODO |  |  |
| C2 | JSON canonical / YAML optional documented | TODO |  |  |
| C3 | failure semantics fail-closed | TODO |  |  |
| D1 | run_nexus_pipeline produces artifacts | TODO |  |  |
| D2 | degraded retrieval path handled | TODO |  |  |
| D3 | receipt quality sufficient | TODO |  |  |
| E1 | no forbidden patterns | TODO |  |  |
| E2 | no secrets in configs/docs | TODO |  |  |
| F1 | review context preserved | TODO |  |  |
| F2 | README discoverability adequate | TODO |  |  |
| G1 | safe to merge | TODO |  |  |

## Decision rule
- Any FAIL in A/B/E => stop merge rehearsal
- Any FAIL in C/D/F => patch candidate branch before merge

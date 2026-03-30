# NEXUS Branch Diff Review Rubric

Use this when the real candidate branch becomes available.

## 1. Identity and naming
- Does the branch introduce `llama_nexus_lab` cleanly?
- Does it preserve or intentionally version any old `llama-throughput-lab` identifiers?
- Is `tool_name` behavior explicit?

## 2. Runtime correctness
- Are retries/timeouts real, not decorative?
- Do degraded/failure states emit receipts instead of pretending success?
- Are artifacts deterministic and reviewable?

## 3. Contract safety
- Are existing throughput contracts unchanged or clearly versioned?
- Are new nexus envelopes/artifacts documented?
- Do tests assert required fields and failure behavior?

## 4. Security/ops hygiene
- No unsafe dynamic execution patterns
- No hardcoded secrets
- Security scanner itself avoids self-flag noise and blind spots

## 5. Mergeability
- Can docs/scaffold be split from runtime code?
- Are rollback seams clear?
- Can this be merged in phases without destabilizing main?

## Scoring
- PASS: clear evidence and tests
- PARTIAL: likely good, but missing proof
- FAIL: contradictions, missing proof, or unsafe behavior

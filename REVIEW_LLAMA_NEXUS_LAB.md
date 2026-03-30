# Review: llama-nexus-lab current state and remaining gaps

## Current state (implemented)

1. **NEXUS-facing contract layer exists**
   - `throughput_lab/identity.py` centralizes identity + contract constants.
   - `docs/nexus_integration.md` documents CLI envelope/receipt expectations.
   - `schemas/nexus_run_envelope_v1.json` and `schemas/nexus_receipt_v1.json` exist.
   - Golden packet tests enforce envelope shape and compatibility behavior.

2. **Governed lane exists and is runnable as a bounded operational skeleton**
   - `llama_nexus_lab/pipeline.py` runs route/retrieve/reason/critique/synthesize/verify stages.
   - `scripts/run_nexus_governed_smoke.py` provides a deterministic governed smoke command.
   - Runtime trace artifacts and verification fields are persisted in run artifacts.

3. **Fail-closed behavior is covered by lightweight deterministic tests**
   - Override unknown key checks in core CLI contract tests.
   - Verification tests cover strict citation behavior.

## Remaining real gaps (not yet implemented in this repo)

1. **No real embeddings/rerank execution path wired into the runtime lane**
   - Config has model profiles for these lanes, but runtime remains a bounded skeleton.

2. **No real remote model-call stack for reason/critique/synthesis in the governed lane**
   - Model routing is represented in receipts/config but not executed as a full multi-model worker system.

3. **Verification remains intentionally lightweight**
   - Coverage + citation URL checks are deterministic and useful, but not a full factuality framework.

## Recommendation for next smallest step

Keep scope bounded: add one adapter-backed reasoner call behind a strict timeout/fail-closed gate while preserving dry-run determinism and existing receipt schema.

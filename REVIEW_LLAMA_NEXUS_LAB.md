# Review: current changes with focus on `llama-nexus-lab`

## Scope reviewed

- Execution core and runtime helper seams (`throughput_lab/execution_core.py`, `throughput_lab/runtime_service.py`).
- Non-interactive entrypoint and packet contract (`scripts/run_core_job.py`).
- Operational framing and architecture docs (`README.md`, `ARCHITECTURE.md`).
- Existing CI and local quality gates (`.github/workflows/ci.yml`, `Makefile`, `tests/test_execution_core.py`).

## What is strong

1. **Clear backend contract for automation and UI adapters**
   - `RunConfig` + packet/receipt model provides deterministic execution and consumable machine output.
   - Good fail-closed checks for endpoint/verification compatibility.

2. **Useful decomposition between orchestration and runtime**
   - `execution_core` handles config/plan/receipt while `runtime_service` encapsulates process lifecycle and HTTP probing.

3. **Testing depth on contract behavior**
   - `tests/test_execution_core.py` validates preflight checks, payload formation, packet content, and smoke receipt semantics.

4. **Practical developer ergonomics**
   - `Makefile` targets and a simple CI workflow make baseline verification straightforward.

## Gaps for `llama-nexus-lab` specifically

1. **No explicit `llama-nexus-lab` component in repo tree**
   - There is currently no `llama_nexus_lab/` package, `llama-nexus-lab` module, or similarly named artifact.

2. **Branding/contract identity still points to `llama-throughput-lab`**
   - CLI envelope reports `"tool_name": "llama-throughput-lab"`.
   - Top-level docs and package naming remain throughput-lab focused.

3. **No documented integration boundary for an external `llama-nexus-lab` repo/service**
   - Architecture explains future TUI/GUI compatibility but does not define a concrete inter-repo protocol versioning strategy, transport, or compatibility guarantees for a separate nexus-lab consumer.

## Recommendations (ordered)

1. **Decide naming strategy now**
   - If `llama-nexus-lab` is a new product identity, centralize `tool_name`/display naming in one constant and update docs consistently.

2. **Add explicit integration contract doc**
   - Create `docs/nexus_integration.md` with:
     - packet/receipt JSON schemas,
     - versioning policy,
     - required vs optional fields,
     - backward-compatibility rules.

3. **Add schema tests for long-term API stability**
   - Add JSON-schema-based tests for dry-run/preflight/smoke envelopes to avoid accidental contract drift.

4. **Add CI checks beyond compile-only linting**
   - Keep current checks, but add `ruff` + `mypy` (or `pyright`) in CI for stronger correctness/static guarantees.

## Risk summary

- **Low implementation risk** in current backend refactor quality.
- **Medium product/integration risk** if `llama-nexus-lab` is expected now: identity and interface are implied, not explicitly versioned or packaged as a distinct addition.

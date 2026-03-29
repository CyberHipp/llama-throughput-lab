# Architecture

## Goal

This fork now has a deterministic, non-interactive execution core that can be called by a future NEXUS-TUI or GUI without embedding UI logic in backend mutation paths.

## Design Decisions

1. **Execution core is explicit and importable**
   - `throughput_lab/execution_core.py` owns normalized config, llama-server command synthesis, and CCR-style receipt emission.
   - It is independent of `dialog`, menus, or `input()`.

2. **UI/launcher remains adapter-only**
   - Existing launcher scripts (`scripts/launcher.py`, `run_llama_tests.py`) remain for operator convenience, but they are not the contract surface.
   - New orchestration callers should target `RunConfig` + `run_with_receipt`.

3. **Receipt-first operation**
   - Every core run writes deterministic artifacts: stdout log, stderr log, exit-code file, and JSON receipt packet.
   - Receipt includes topology/config snapshots and bounded next step.

4. **Compatibility preserved where sensible**
   - `RunConfig.from_env()` preserves current `LLAMA_*` environment variable habits while normalizing to a typed object.

5. **Fail-closed defaults**
   - Missing/invalid explicit config does not silently mutate runtime assumptions.
   - Receipt marks verification as `fail` when command exits non-zero.

## Repo seam for NEXUS clients

- Input contract: `RunConfig` (or JSON equivalent in `scripts/run_core_job.py`).
- Output contract: receipt JSON path + artifact files.
- Execution remains backend-only and non-interactive.

## Why adaptation instead of rewrite

The existing repo already has useful execution primitives (server start/wait, HTTP probes, arg parsing, topology utilities). The patch extracts a core contract around those concerns without deleting existing benchmark scripts, preserving upstream diffability and reducing migration risk.

## Request contract (single-smoke lane)

`RunConfig` now owns endpoint-aware payload building:
- `/completion`: prompt-style payload (`prompt`, `n_predict`, `temperature`, optional `seed`, optional `stop`)
- `/v1/chat/completions`: message payload (`messages`, `max_tokens`, `temperature`, optional `seed`, optional `stop`)

Fail-closed behavior:
- unsupported endpoint mode values are rejected during env normalization.
- `system_prompt` with `/completion` fails closed and requires chat-completions mode.
- plan/execute path currently enforces `topology_mode=single` for the first smoke lane.

## Dry-run / plan packet

`build_run_plan(...)` emits a deterministic packet for TUI/GUI orchestration without launching runtime:
- resolved command
- resolved endpoint path
- resolved request payload
- resolved topology
- deterministic artifact paths
- verification target + placeholders

## Runtime helper promotion

The minimum reusable lifecycle/probe subset was promoted from test-only helpers into `throughput_lab/runtime_service.py`:
- readiness probing (`wait_for_server_ready`)
- JSON POST helper (`post_json`)
- long-running server process lifecycle (`launch_server_process` / `stop_server_process`)
- token/tps extraction for smoke metrics

This keeps backend smoke execution out of `tests/` and provides a stable seam for future NEXUS clients.

## Smoke harness API

`execute_single_smoke_with_receipt(...)` is the canonical first-lane backend API:
- uses `build_run_plan(...)`
- starts server as long-running process
- waits readiness
- sends exactly one deterministic request using normalized endpoint/payload
- writes request/response artifacts
- emits smoke receipt fields for readiness/request/overall verification and metrics summary
- always performs clean shutdown

## Verification contract

Smoke verification is intentionally small and explicit:
- `run_preflight_checks(...)` for fail-closed pre-execution checks
- `parse_smoke_response(...)` for endpoint-aware extracted-text normalization
- `verify_smoke_response(...)` for policy modes (`NON_EMPTY`, `EXACT`, `CONTAINS`)

Endpoint request-model contract:
- Native `/completion` is model-local and does not require request `model`.
- OpenAI-compatible `/v1/chat/completions` and `/v1/completions` require `request_model`; missing value fails closed in payload generation.

Receipt/result classification is separated into:
- preflight
- readiness
- response parse
- semantic verification
- controlled shutdown
- overall verification

This keeps verification logic in backend runtime code (not test-only code), and keeps the same contract consumable by future TUI/GUI adapters.

Runtime env overlay contract:
- `RunConfig.runtime_env` carries non-secret process env overlays (e.g. `LD_LIBRARY_PATH`, `CUDA_VISIBLE_DEVICES`).
- Overlay is applied only to launched `llama-server` process and is surfaced in dry-run/receipt as `resolved_runtime_env`.

Controlled shutdown semantics:
- Smoke intentionally stops a long-running server after one request.
- Overall success depends on controlled-shutdown classification, not only `exit_code == 0`, to avoid false failures on signal-style termination codes.

## Local profile override layer

The first real 3B smoke lane needs portable committed defaults and machine-specific runtime binding without polluting shared config.

Implementation:
- Canonical base profile remains committed at `configs/first_3b_single_smoke.json`.
- Optional machine-local override is passed via `--config-override-json` and is expected under `configs/local/*.json` (gitignored).
- CLI performs deterministic merge before `RunConfig` materialization.

Merge contract:
- override scalars replace base scalars
- override arrays replace base arrays entirely
- override `runtime_env` replaces base `runtime_env` as a full dict
- unknown override keys fail closed before merge
- enum validation remains fail-closed through `RunConfig` construction

This gives one clear seam for local node paths (`model_path`, `llama_server_bin`), runtime env, and optional port binding, while preserving stable packet/receipt envelopes.

Canonical packet envelope:
- `packet_version`
- `mode`
- `status`
- `run_id`
- `intent`
- `tool_name`
- `receipt_path`
- `failure_summary`
- `next_step`
- `data`

The CLI now exposes three contract modes with this envelope:
- `--dry-run`
- `--preflight-only`
- `--single-smoke`

Receipt path consistency:
- `--dry-run` / `--preflight-only` emit envelope-only packets and set `receipt_path=null`.
- `--single-smoke` emits a receipt file and reports its path in the envelope.

## llama-nexus-lab architecture (new)

### Objective

Provide a deterministic, bounded researcher pipeline that combines retrieval + reasoning + critique + synthesis while preserving machine-readable receipts and reproducible artifacts.

### Decisions

1. **Separated package namespace**
   - Added `llama_nexus_lab/` to prevent cross-coupling with throughput-only internals.

2. **Config-driven routing**
   - `configs/nexus/default.yaml|json` define search/pipeline/runtime knobs and task->model routing.

3. **Bounded loops by default**
   - `max_iterations` exists in config and defaults to 3 to avoid runaway agent loops.

4. **Receipt-first outputs**
   - Every run writes answer, receipt, and evidence artifacts for auditability.

5. **Simple dependency policy**
   - Uses Python stdlib for deterministic operation without extra runtime dependencies.

### Why this shape

This keeps the existing throughput/smoke core stable while introducing a production-friendly research orchestrator that can run dry-run offline and online retrieval modes without invasive changes to existing code paths.

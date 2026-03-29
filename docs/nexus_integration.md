# NEXUS Integration Contract (v1)

## Scope

This document defines the **NEXUS-facing backend contract** for consuming `llama-throughput-lab` as a deterministic, non-interactive execution primitive. It covers CLI envelope shape, receipt artifacts, compatibility rules, and failure expectations for this pass.

## Input contract

Supported inputs to `scripts/run_core_job.py`:

1. Environment-based `RunConfig` via `LLAMA_*` variables.
2. Explicit JSON config via `--config-json <path>`.
3. Optional local override via `--config-override-json <path>` (fails closed on unknown keys).

### CLI modes

- `--dry-run`
- `--preflight-only`
- `--single-smoke`

## Output contract

The CLI emits a packet envelope in JSON for dry-run, preflight-only, and single-smoke modes.

Required envelope keys:

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

Optional envelope key:
- `timestamp_utc`

`receipt_path` is nullable for dry-run/preflight and expected to be non-null for single-smoke.

## Required vs optional fields

Required by all consumers:
- envelope required keys listed above.

Optional/nullable:
- `timestamp_utc`
- `receipt_path` for non-execution modes

## Versioning policy

- Product identity constants are centralized in `throughput_lab/identity.py`.
- Contract identifier for this pass: `nexus-contract-v1`.
- Envelope `packet_version` remains stable at `1.0` for backward compatibility.

## Backward compatibility rule

Existing envelope keys are preserved; new metadata is additive only in `data`.
Consumers must tolerate additive keys.

## Failure-class expectations

- Config normalization or override violations fail closed with non-zero exit.
- Preflight failures produce structured failure envelopes.
- Smoke failures preserve deterministic envelope shape with failure `status`.

## Artifact expectations

When execution paths run, artifacts are emitted under the configured output directory:
- `*.stdout.log`
- `*.stderr.log`
- `*.receipt.json`
- request/response sidecar files (smoke mode)

## Out of scope in this pass

- Repository or package renaming
- GUI/TUI implementation
- New benchmark topology features
- Live-server requirement for minimum contract test bar

# NEXUS queue mode (sequential bounded runs)

Queue mode allows multiple gauntlets to run sequentially via the TUI.

## Behavior

- Enqueue one or more gauntlets.
- Run sequentially with one of:
  - stop-on-fail
  - continue-on-fail

Queue artifacts:
- manifest: `artifacts/nexus/tui_runs/queue/<queue_id>.json`
- receipt: `artifacts/nexus/tui_runs/queue/<queue_id>_receipt.json`

Queue item receipt fields:
- `gauntlet_name`
- `config_path`
- `run_id` (when launched)
- `status` (`pass|fail|skipped`)
- `reason`
- `artifacts`

This mode is deterministic and transport-independent.

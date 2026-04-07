# NEXUS Cockpit v2 Contract (v1)

Cockpit v2 exposes three machine-readable surfaces:

1. Snapshot export: `python scripts/run_nexus_tui.py --dump-state`
2. Action bridge: `--action-json` / `--action-file`
3. Durable action receipts under `artifacts/nexus/cockpit_state/receipts/`

Versioned schemas:
- `schemas/nexus_cockpit_snapshot_v1.json`
- `schemas/nexus_cockpit_action_v1.json`
- `schemas/nexus_cockpit_action_result_v1.json`

Validate artifacts on demand:

```bash
python scripts/validate_nexus_cockpit_contract.py --kind snapshot --json-file tests/fixtures/cockpit/snapshot_example.json
python scripts/validate_nexus_cockpit_contract.py --kind action --json-file tests/fixtures/cockpit/action_load_preset.json
python scripts/validate_nexus_cockpit_contract.py --kind result --json-file tests/fixtures/cockpit/action_result_example.json
```

# NEXUS TUI scaffold (VorteX gauntlets)

This TUI is an **operator-facing scaffold** for bounded custom gauntlet runs.
It is intentionally small and wraps existing scripts instead of replacing runtime logic.

## Non-goals

- Not a full orchestration platform.
- Not a replacement for core pipeline scripts.
- No new dependencies; stdlib only.

## Launch

```bash
python scripts/run_nexus_tui.py
```

Menu actions:
1. New Gauntlet
2. Load Gauntlet Preset
3. Dry-Run Preview
4. Launch One Run
5. Show Recent Artifacts
6. Exit

## Presets

Presets are persisted to:

- `configs/nexus/gauntlets/<name>.json`

Preset format:

```json
{
  "gauntlet_name": "sample",
  "query": "How should we tune strict citation mode?",
  "max_search_intents": 6,
  "strict_citation_required": true,
  "dry_run": true,
  "require_verify_pass": true
}
```

## Runtime config generation

Per-run config snapshots are written to:

- `artifacts/nexus/tui_runs/<run_id>/config.json`

The canonical `configs/nexus/default.json` is never modified in place.

## Launch behavior

- If `require_verify_pass=true`, the TUI invokes `scripts/run_nexus_governed_smoke.py`.
- Otherwise it invokes `scripts/run_nexus_pipeline.py`.

At the end of each action, the TUI prints machine-readable JSON including run id, gauntlet, config path, artifacts, and verification status when available.

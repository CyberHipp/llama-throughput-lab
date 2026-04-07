# NEXUS gauntlet preset library

This document describes bundled preset templates under:

- `configs/nexus/gauntlets/presets/`

Available presets:
- `vortex_fast_scan.json`
- `vortex_deep_verify.json`
- `gauntlet_conservative.json`
- `gauntlet_balanced.json`

Each preset includes:
- `gauntlet_name`
- `query_template` (supports `{topic}` placeholder)
- `max_search_intents`
- `strict_citation_required`
- `dry_run`
- `require_verify_pass`
- optional metadata tags (`mode`, `risk_level`, `notes`)

Use these as bounded operator defaults; they are not a full policy engine.

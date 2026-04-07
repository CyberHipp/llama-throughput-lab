#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LEDGER="$ROOT_DIR/registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv"

if [[ ! -f "$LEDGER" ]]; then
  echo "missing ledger: $LEDGER" >&2
  exit 1
fi

run_id="watchdog-$(date -u +%Y%m%dT%H%M%SZ)"
line="$run_id\t$(date -u +%Y-%m-%dT%H:%M:%SZ)\tgmail_control_watchdog\tok\thealth-check"
printf '%b\n' "$line" >> "$LEDGER"
echo "watchdog ledger updated: $run_id"

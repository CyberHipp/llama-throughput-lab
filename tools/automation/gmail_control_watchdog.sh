#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR_DEFAULT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROOT_DIR="${AUTOMATION_ROOT_DIR:-$ROOT_DIR_DEFAULT}"
SEED_LEDGER="registries/EMAIL_CONTROL_WATCHDOG_LEDGER_v1.tsv"
LEDGER="${AUTOMATION_STATE_DIR:-$ROOT_DIR/artifacts/automation_state}/$SEED_LEDGER"

mkdir -p "$(dirname "$LEDGER")"
if [[ ! -f "$LEDGER" ]]; then
  if [[ ! -f "$ROOT_DIR/$SEED_LEDGER" ]]; then
    echo "missing seed ledger: $ROOT_DIR/$SEED_LEDGER" >&2
    exit 1
  fi
  cp "$ROOT_DIR/$SEED_LEDGER" "$LEDGER"
fi

run_id="watchdog-$(date -u +%Y%m%dT%H%M%SZ)"
line="$run_id\t$(date -u +%Y-%m-%dT%H:%M:%SZ)\tgmail_control_watchdog\tok\thealth-check"
printf '%b\n' "$line" >> "$LEDGER"
echo "watchdog ledger updated: $run_id"
echo "runtime ledger path: $LEDGER"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_OUTPUT="$($ROOT_DIR/tools/automation/gmail_hourly_report.sh)"

echo "[DRY-RUN] would send report with body:"
echo "$REPORT_OUTPUT"

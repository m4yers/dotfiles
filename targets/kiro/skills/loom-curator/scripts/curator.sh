#!/usr/bin/env bash
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    CURATOR_SH="$0" \
    uv run --project "$SCRIPTS_DIR/curator" \
    python -m curator "$@"

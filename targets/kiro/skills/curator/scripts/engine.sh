#!/usr/bin/env bash
# engine.sh — shim for `python -m engine` via uv.
# All curator operations route through here.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/engine" \
    python -m engine "$@"

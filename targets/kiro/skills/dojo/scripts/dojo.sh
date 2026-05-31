#!/usr/bin/env bash
# Shim for the loom-driven dojo skill (create / update / review).
# Forwards args to the dojo Python module via uv.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}/dojo${PYTHONPATH:+:${PYTHONPATH}}" \
    DOJO_SH="$0" \
    uv run --project "$SCRIPTS_DIR/dojo" \
    python -m dojo "$@"

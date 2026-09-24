#!/usr/bin/env bash
# Shim for the loom-driven notepad skill.
# Forwards args to the notepad Python module via uv.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/notepad" \
    python -m notepad "$@"

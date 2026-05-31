#!/usr/bin/env bash
# Shim for the loom-driven think skill.
# Forwards args to the think Python module via uv.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}/think${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/think" \
    python -m think "$@"

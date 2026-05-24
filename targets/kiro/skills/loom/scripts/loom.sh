#!/usr/bin/env bash
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}/loom${PYTHONPATH:+:${PYTHONPATH}}" \
    LOOM_SH="$0" \
    uv run --project "$SCRIPTS_DIR/loom" \
    python -m loom "$@"

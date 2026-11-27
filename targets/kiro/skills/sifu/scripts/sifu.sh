#!/usr/bin/env bash
# Shim for the sifu Python package (loom tool tasks, autochecks, report).
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
exec uv run --quiet --project "$SCRIPTS_DIR/sifu" python -m sifu "$@"

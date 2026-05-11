#!/usr/bin/env bash
# source.sh — shim for `python -m source` via uv.
# Source acquisition: fetch (URL / local → vault file + workdir source.md)
# and convert (vault file → workdir source.md).
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/source" \
    python -m source "$@"

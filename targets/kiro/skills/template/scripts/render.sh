#!/usr/bin/env bash
# render.sh — shim for `python -m renderer` via uv.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec env PYTHONPATH="${DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$DIR/renderer" python -m renderer "$@"

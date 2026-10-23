#!/usr/bin/env bash
# run-editor.sh — shim for `python -m editor` via uv.
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --python 3.12 \
    --project "$SCRIPTS_DIR/editor" \
    python -m editor "$@"

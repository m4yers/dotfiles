#!/usr/bin/env bash
# live-doc.sh — shim for the live-doc skill. Dispatches to the
# `live_doc` Python package (subcommands `create` and `ingest`).
# Loom calls go directly through $LOOM in SKILL.md; this shim does
# not forward to loom.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}/live-doc${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/live-doc" \
    python -m live_doc "$@"

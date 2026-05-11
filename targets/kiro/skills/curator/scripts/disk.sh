#!/usr/bin/env bash
# disk.sh — shim for `python -m disk` via uv.
# Workdir lifecycle + per-item JSON builders + prompt rendering +
# verdict aggregation + report-vars. Every canonical JSON artifact
# in the pipeline's workdir is produced through this tool.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/disk" \
    python -m disk "$@"

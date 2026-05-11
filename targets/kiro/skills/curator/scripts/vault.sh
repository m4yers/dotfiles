#!/usr/bin/env bash
# vault.sh — shim for `python -m vault` via uv.
# Every vault operation (page CRUD, materialize, apply-plan, verify-
# batch, context, lint, commit, recent) routes through here.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/vault" \
    python -m vault "$@"

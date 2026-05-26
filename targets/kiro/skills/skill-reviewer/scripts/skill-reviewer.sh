#!/usr/bin/env bash
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}/skill-reviewer${PYTHONPATH:+:${PYTHONPATH}}" \
    REVIEWER_SH="$0" \
    uv run --project "$SCRIPTS_DIR/skill-reviewer" \
    python -m skill_reviewer "$@"

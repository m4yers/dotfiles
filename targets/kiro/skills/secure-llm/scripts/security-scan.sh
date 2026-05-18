#!/usr/bin/env bash
# security-scan.sh — standalone CLI wrapper for the security_scan
# package. Mirrors curator.sh: resolves the scripts dir relative
# to itself so the wrapper works regardless of CWD, runs the
# package's own uv venv.
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/security_scan" \
    python -m security_scan "$@"

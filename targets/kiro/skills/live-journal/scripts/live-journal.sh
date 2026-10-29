#!/usr/bin/env bash
# live-journal.sh — shim for the live-journal skill. Dispatches to the
# `live_journal` Python package (subcommands `create`, `open`, `topic`,
# `section`, `appendix`).
set -euo pipefail
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}/live-journal${PYTHONPATH:+:${PYTHONPATH}}" \
    python3 -m live_journal "$@"

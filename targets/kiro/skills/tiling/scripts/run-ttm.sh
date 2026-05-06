#!/usr/bin/env bash
# run-ttm.sh — shim for tmux-tiling-manager.py
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run --python 3.12 \
  --project "$SCRIPTS_DIR" \
  python "$SCRIPTS_DIR/tmux-tiling-manager.py" "$@"

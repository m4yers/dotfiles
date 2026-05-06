#!/usr/bin/env bash
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run --python 3.12 \
  --project "$SCRIPTS_DIR" \
  python "$SCRIPTS_DIR/editor.py" "$@"

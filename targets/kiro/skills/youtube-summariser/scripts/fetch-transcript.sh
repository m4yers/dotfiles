#!/usr/bin/env bash
# fetch-transcript.sh — shim for fetch_transcript.py via uv.
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec uv run --python 3.12 \
  --project "$SCRIPTS_DIR/fetch-transcript" \
  python "$SCRIPTS_DIR/fetch-transcript/fetch_transcript.py" "$@"

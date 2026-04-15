#!/usr/bin/env bash
exec uv run --python 3.12 \
  --project ~/.kiro/skills/tools/editor/scripts \
  python ~/.kiro/skills/tools/editor/scripts/editor.py "$@"

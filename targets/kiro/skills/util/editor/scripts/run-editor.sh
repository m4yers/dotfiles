#!/usr/bin/env bash
exec uv run --python 3.12 \
  --project ~/.kiro/skills/util/editor/scripts \
  python ~/.kiro/skills/util/editor/scripts/editor.py "$@"

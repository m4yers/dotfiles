#!/usr/bin/env bash
exec uv run --python 3.12 \
  --project ~/.kiro/skills/tools/tiling/scripts \
  python ~/.kiro/skills/tools/tiling/scripts/tmux-tiling-manager.py "$@"

#!/usr/bin/env bash
exec uv run --python 3.12 \
  --project ~/.kiro/skills/util/tiling/scripts \
  python ~/.kiro/skills/util/tiling/scripts/tmux-tiling-manager.py "$@"

#!/usr/bin/env bash
#
# List currently-installed skill namespaces by inspecting ~/.kiro/skills/.
# Each top-level entry that is a directory (symlink or real) counts as one
# namespace. Prints one name per line.
#
# Usage:
#   list-namespaces.sh
#
# Exit 1 if ~/.kiro/skills/ does not exist.

set -e

SKILLS_DIR="$HOME/.kiro/skills"

if [ ! -d "$SKILLS_DIR" ]; then
  echo "error: $SKILLS_DIR does not exist" >&2
  exit 1
fi

shopt -s nullglob
for entry in "$SKILLS_DIR"/*; do
  if [ -d "$entry" ]; then
    basename "$entry"
  fi
done

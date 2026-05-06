#!/usr/bin/env python3
"""Extract the 'type' field from a skill's SKILL.md frontmatter.

Usage: extract-type.py <skill-dir>
Prints the type value (e.g. "workflow") to stdout.
"""
import sys
from pathlib import Path

skill_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if not skill_dir or not skill_dir.is_dir():
    print(f"Usage: {sys.argv[0]} <skill-dir>", file=sys.stderr)
    sys.exit(2)

skill_md = skill_dir / "SKILL.md"
if not skill_md.exists():
    print(f"ERROR: {skill_md} not found", file=sys.stderr)
    sys.exit(1)

in_frontmatter = False
for line in skill_md.read_text().splitlines():
    stripped = line.strip()
    if stripped == "---":
        if not in_frontmatter:
            in_frontmatter = True
            continue
        break  # closing delimiter — field not found
    if in_frontmatter and stripped.startswith("type:"):
        print(stripped.split(":", 1)[1].strip())
        sys.exit(0)

print("ERROR: no 'type' field in frontmatter", file=sys.stderr)
sys.exit(1)

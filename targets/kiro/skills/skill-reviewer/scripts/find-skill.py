#!/usr/bin/env python3
"""Find a skill directory by name, optionally filtered by category.

Usage: find-skill.py <name> [<category>]
Prints the absolute path. Exits 1 if not found.
"""
import sys
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Usage: find-skill.py <name> [<category>]", file=sys.stderr)
        sys.exit(1)
    name = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else None
    base = Path.home() / ".kiro" / "skills"
    cats = [category] if category else ["dev", "diagnostics", "util"]
    for cat in cats:
        candidate = base / cat / name
        if (candidate / "SKILL.md").is_file():
            print(candidate)
            return
    print(f"skill '{name}' not found", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Find a skill directory by name.

Usage: find-skill.py <name>

Prints the absolute path on success. Exits 1 if not found, 2 if
ambiguous (multiple matches).

Searches ~/.kiro/skills/**/<name>/SKILL.md so any namespace and any
depth is supported. If more than one SKILL.md is found with the same
parent directory name, all candidates are printed to stderr and the
script exits 2 — the caller must disambiguate.
"""
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: find-skill.py <name>", file=sys.stderr)
        sys.exit(1)
    name = sys.argv[1]
    base = Path.home() / ".kiro" / "skills"

    matches = sorted(base.glob(f"**/{name}/SKILL.md", recurse_symlinks=True))
    if not matches:
        print(f"skill '{name}' not found", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(
            f"skill '{name}' is ambiguous; found in multiple namespaces:",
            file=sys.stderr,
        )
        for m in matches:
            print(f"  {m.parent}", file=sys.stderr)
        print(
            "disambiguate by passing the full path from the list above",
            file=sys.stderr,
        )
        sys.exit(2)
    print(matches[0].parent)


if __name__ == "__main__":
    main()

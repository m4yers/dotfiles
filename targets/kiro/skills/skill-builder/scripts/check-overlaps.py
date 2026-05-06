#!/usr/bin/env python3
"""Check trigger phrase overlaps across skills.

Walks ~/.kiro/skills/**/SKILL.md so any namespace and any nesting depth
is supported (e.g. home/<skill> or aws/util/<skill>).
"""
import argparse
import re
import sys
from pathlib import Path

SKILLS_ROOT = Path.home() / ".kiro" / "skills"


def parse_description(path):
    """Extract description from SKILL.md frontmatter."""
    try:
        text = path.read_text()
    except OSError:
        return None
    m = re.search(
        r'^description:\s*(.+?)(?:\n---|\n[a-z]+:)',
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return None
    return ' '.join(m.group(1).split())


def extract_triggers(desc):
    """Pull quoted trigger phrases from description."""
    return re.findall(r'"([^"]+)"', desc)


def main():
    parser = argparse.ArgumentParser(
        description="Check trigger phrase overlaps across skills.")
    parser.add_argument("skill_name", help="Skill name to check")
    args = parser.parse_args()

    target = args.skill_name

    # Find target skill (glob any depth).
    target_matches = sorted(SKILLS_ROOT.glob(f"**/{target}/SKILL.md"))
    if not target_matches:
        print(f"Skill '{target}' not found")
        sys.exit(1)
    if len(target_matches) > 1:
        print(f"Skill '{target}' is ambiguous; matches:")
        for m in target_matches:
            print(f"  {m.parent.relative_to(SKILLS_ROOT)}")
        sys.exit(2)
    target_path = target_matches[0]

    target_desc = parse_description(target_path)
    if not target_desc:
        print(f"Cannot parse description from {target_path}")
        sys.exit(1)

    target_triggers = set(t.lower() for t in extract_triggers(target_desc))
    if not target_triggers:
        print(f"No quoted trigger phrases found in '{target}'")
        sys.exit(1)

    # Scan every other SKILL.md in the tree.
    overlaps = []
    for skill_md in sorted(SKILLS_ROOT.glob("**/SKILL.md")):
        if skill_md == target_path:
            continue
        desc = parse_description(skill_md)
        if not desc:
            continue
        other_triggers = set(t.lower() for t in extract_triggers(desc))
        common = target_triggers & other_triggers
        if common:
            rel = skill_md.parent.relative_to(SKILLS_ROOT)
            overlaps.append((str(rel), common))

    if overlaps:
        print(f"Trigger overlaps for '{target}':")
        for name, phrases in overlaps:
            print(f"  {name}: {', '.join(sorted(phrases))}")
    else:
        print(f"No trigger overlaps found for '{target}'")


if __name__ == "__main__":
    main()

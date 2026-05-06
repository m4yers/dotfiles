#!/usr/bin/env python3
"""Check trigger phrase and functionality overlaps across skills."""
import argparse
import os
import re
import sys

SKILLS_ROOT = os.path.expanduser("~/.kiro/skills")


def parse_description(path):
    """Extract description from SKILL.md frontmatter."""
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return None
    m = re.search(r'^description:\s*(.+?)(?:\n---|\n[a-z]+:)', text,
                  re.MULTILINE | re.DOTALL)
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
    parser.add_argument("category", nargs="?", default=None,
                        help="Category (dev/diagnostics/util)")
    args = parser.parse_args()

    target = args.skill_name
    category = args.category

    # Find target skill
    target_path = None
    for cat in ([category] if category else os.listdir(SKILLS_ROOT)):
        p = os.path.join(SKILLS_ROOT, cat, target, "SKILL.md")
        if os.path.isfile(p):
            target_path = p
            break
    if not target_path:
        print(f"Skill '{target}' not found")
        sys.exit(1)

    target_desc = parse_description(target_path)
    if not target_desc:
        print(f"Cannot parse description from {target_path}")
        sys.exit(1)

    target_triggers = set(t.lower() for t in extract_triggers(target_desc))
    if not target_triggers:
        print(f"No quoted trigger phrases found in '{target}'")
        sys.exit(1)

    # Scan all other skills
    overlaps = []
    for cat in sorted(os.listdir(SKILLS_ROOT)):
        cat_dir = os.path.join(SKILLS_ROOT, cat)
        if not os.path.isdir(cat_dir):
            continue
        for skill in sorted(os.listdir(cat_dir)):
            if skill == target:
                continue
            p = os.path.join(cat_dir, skill, "SKILL.md")
            desc = parse_description(p)
            if not desc:
                continue
            other_triggers = set(t.lower() for t in extract_triggers(desc))
            common = target_triggers & other_triggers
            if common:
                overlaps.append((f"{cat}/{skill}", common))

    if overlaps:
        print(f"Trigger overlaps for '{target}':")
        for name, phrases in overlaps:
            print(f"  {name}: {', '.join(sorted(phrases))}")
    else:
        print(f"No trigger overlaps found for '{target}'")


if __name__ == "__main__":
    main()

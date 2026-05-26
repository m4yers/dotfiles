"""Locate a skill by name and extract its frontmatter type.

Replaces the old find-skill.py + extract-type.py scripts. Walks
~/.kiro/skills/ following symlinks so namespace symlinks work,
and extracts the `type` field from the SKILL.md frontmatter.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

SKILLS_ROOT = Path.home() / ".kiro" / "skills"


def find_skill_dir(name: str, category: Optional[str] = None) -> Path:
    """Find the skill directory matching `name`.

    If `category` is given, restrict to that namespace
    (~/.kiro/skills/<category>/<name>). Otherwise walk all
    namespaces; ambiguous matches raise FileExistsError.
    """
    if category:
        candidate = SKILLS_ROOT / category / name
        if (candidate / "SKILL.md").is_file():
            return candidate
        raise FileNotFoundError(
            f"skill '{name}' not found in category '{category}'")

    matches = []
    # followlinks=True — namespace symlinks (home -> dotfiles)
    # need to be traversed to find skills.
    for dirpath, _, _ in os.walk(SKILLS_ROOT, followlinks=True):
        if os.path.basename(dirpath) == name:
            skill_md = Path(dirpath) / "SKILL.md"
            if skill_md.is_file():
                matches.append(Path(dirpath))
    matches = sorted(set(matches))
    if not matches:
        raise FileNotFoundError(f"skill '{name}' not found")
    if len(matches) > 1:
        listing = "\n".join(f"  {m}" for m in matches)
        raise FileExistsError(
            f"skill '{name}' is ambiguous; pass --category:\n{listing}")
    return matches[0]


def extract_type(skill_dir: Path) -> str:
    """Extract the `type` field from SKILL.md frontmatter."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"{skill_md} not found")

    in_frontmatter = False
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            break
        if in_frontmatter and stripped.startswith("type:"):
            return stripped.split(":", 1)[1].strip()

    raise ValueError(f"no 'type' field in {skill_md}")


# Map skill_dir absolute path → category by inspecting position
# under SKILLS_ROOT. The category is the first path component
# below SKILLS_ROOT (e.g. 'home', 'aws').
def derive_category(skill_dir: Path) -> str:
    """Derive category from the skill's path under SKILLS_ROOT."""
    try:
        rel = skill_dir.resolve().relative_to(SKILLS_ROOT.resolve())
    except ValueError:
        return "unknown"
    parts = rel.parts
    return parts[0] if parts else "unknown"


# Used by `pipeline locate` subcommand to assemble locate.yaml.
def build_locate_output(name: str, category: Optional[str]) -> dict:
    skill_dir = find_skill_dir(name, category)
    typ = extract_type(skill_dir)
    cat = category or derive_category(skill_dir)
    return {
        "skill_dir": str(skill_dir),
        "name": name,
        "category": cat,
        "type": typ,
    }

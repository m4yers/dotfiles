"""Tool task: scan SKILL.md descriptions for overlapping trigger
phrases between a candidate skill and every installed skill.

Used in the create pipeline to warn the user about router
collisions before any files are written. The candidate skill
does not exist on disk yet — its name and description come
from the `gather-create` task output.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from sifu.autochecks._helpers import parse_frontmatter
from sifu.tasks import find_skill
from sifu.utils import SKILLS_ROOT


def _parse_description(path: Path) -> Optional[str]:
    """Description value from SKILL.md frontmatter (shared parser)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    fields, _ = parse_frontmatter(lines)
    return fields["description"][0] if "description" in fields else None


def _extract_triggers(desc: str) -> set[str]:
    """Lower-cased quoted phrases from a description string."""
    return {t.lower() for t in re.findall(r'"([^"]+)"', desc)}


def run(name: str, description: str) -> dict:
    """Scan installed skills for trigger overlaps.

    Skips any existing skill named `name` (it might be the
    candidate being re-run, or simply an irrelevant peer).
    Returns a dict matching `loom/check-overlaps/io.yaml` output.
    """
    candidate_triggers = _extract_triggers(description)
    if not candidate_triggers:
        return {"has_overlaps": False, "overlaps": []}

    overlaps = []
    for skill in find_skill._scan_landscape()["skills"]:
        if skill["name"] == name:
            continue
        skill_dir = Path(skill["path"])
        other_desc = _parse_description(skill_dir / "SKILL.md")
        if not other_desc:
            continue
        common = candidate_triggers & _extract_triggers(other_desc)
        if common:
            rel = skill_dir.relative_to(SKILLS_ROOT)
            overlaps.append({
                "skill": str(rel),
                "reason": ", ".join(sorted(common)),
            })

    overlaps.sort(key=lambda o: o["skill"])
    return {"has_overlaps": bool(overlaps), "overlaps": overlaps}



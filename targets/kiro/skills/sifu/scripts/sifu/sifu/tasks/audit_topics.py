"""Tool task: detect the topics a skill directory exhibits.

Vocabulary in references/rule-codes.md §4. audit-checks selects the
references whose ``Applies`` meets these topics.
"""
from __future__ import annotations

import re
from pathlib import Path

from sifu import rules

_SUBAGENT_RE = re.compile(r"sub-?agent", re.IGNORECASE)


def run(skill_dir: str, skill_type: str) -> dict:
    root = Path(skill_dir)
    topics = ["always", f"type:{skill_type}"]
    loom_dirs = [p for p in root.glob("loom*") if p.is_dir()]
    probes = {
        "scripts": (root / "scripts").is_dir(),
        "python": any(root.rglob("*.py")),
        "bash": any(root.rglob("*.sh")),
        "loom": bool(loom_dirs),
        "prompts": any(p for d in loom_dirs for p in d.rglob("*.md.j2")),
        "templates": (root / "templates").is_dir(),
        "schemas": (root / "schemas").is_dir(),
        "references": (root / "references").is_dir(),
        "subagents": bool(_SUBAGENT_RE.search(
            (root / "SKILL.md").read_text(encoding="utf-8")
            if (root / "SKILL.md").is_file() else "")),
        "rule-refs": any(
            rules.CODE_RE.match(line)
            for p in (root / "references").glob("*.md")
            for line in p.read_text(encoding="utf-8").splitlines()[:6]
        ) if (root / "references").is_dir() else False,
    }
    topics.extend(t for t, hit in probes.items() if hit)
    return {"topics": topics}

"""Tool task: verify the namespace exists and the skill does not.

`location` MUST point to an existing directory under
`~/.kiro/skills/`. `<location>/<name>/` MUST NOT exist (we
refuse to overwrite). Exits non-zero on either failure.
"""
from __future__ import annotations

from sifu.utils import SKILLS_ROOT


def run(location: str, name: str) -> dict:
    """Returns `{ok: bool, error?: str}`."""
    ns_dir = SKILLS_ROOT / location
    if not ns_dir.is_dir():
        return {
            "ok": False,
            "error": f"namespace '{location}' does not exist at {ns_dir}",
        }
    skill_dir = ns_dir / name
    if skill_dir.exists():
        return {
            "ok": False,
            "error": f"skill directory already exists at {skill_dir}",
        }
    return {"ok": True}



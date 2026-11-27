"""Tool task: validate that a candidate skill name is kebab-case.

``run()`` returns ``{ok, error?}`` and does not exit. On
``ok: false``, ``loomtasks._check_name`` calls ``fail`` so loom
marks the task ``failed``.
"""
from __future__ import annotations

import re


_KEBAB = re.compile(r"^[a-z][a-z0-9-]*$")


def run(name: str) -> dict:
    """Returns `{ok: bool, error?: str}`. Does NOT exit."""
    if _KEBAB.match(name):
        return {"ok": True}
    return {
        "ok": False,
        "error": (
            f"name '{name}' must be kebab-case "
            "(lowercase letters, digits, and hyphens; starts with a letter)"
        ),
    }



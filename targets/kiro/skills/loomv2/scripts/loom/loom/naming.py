"""Shared naming helpers so scaffold and dispatch cannot drift."""
from __future__ import annotations

import re
from pathlib import Path


def snake_case_task_name(name: str) -> str:
    """Convert a kebab-case task id (local segment) to snake_case.

    The tool.py function name contract is: ``def <snake_case>(inp)``.
    Both ``scaffold/task.py`` (which writes the template) and
    ``engine/tool_dispatch.py`` (which looks the function up) must
    agree on this transform, so both call this helper.
    """
    return re.sub(r"[-]+", "_", name)


def pascal_case_task_name(name: str) -> str:
    """Convert a kebab-case task id (local segment) to PascalCase.

    Used to name the generated ``<TaskName>Input`` / ``<TaskName>Output``
    dataclasses in a tool task's ``tool.py``. Both ``scaffold/task.py``
    (which writes them) and ``engine/tool_dispatch.py`` (which looks
    them up) call this helper, so the names cannot drift.

    ``greet-user`` -> ``GreetUser`` -> classes ``GreetUserInput`` /
    ``GreetUserOutput``.
    """
    return "".join(part.capitalize() for part in re.split(r"[-_]+", name) if part)



def derive_skill_name(loom_root: Path) -> str:
    """Derive the consumer-skill name from a ``loom_root`` path.

    Used by ``runtime init`` when the caller omits the workdir
    positional to build the auto workdir at
    ``/tmp/<skill_name>/<uuid4-hex-12>/``.

    Rule: if ``loom_root``'s basename is exactly ``loom`` (the
    conventional child folder of a skill directory, e.g.
    ``.../skills/aws/diagnostics/rca/loom``), the skill name is the
    parent directory's basename (``rca``). Otherwise the skill name
    is ``loom_root``'s own basename — this catches loom-roots that
    were named after the skill directly (e.g. ``hello-graph``) rather
    than nested under a ``loom/`` subfolder.
    """
    root = Path(loom_root)
    if root.name == "loom":
        return root.parent.name
    return root.name

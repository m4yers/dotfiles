"""Shared naming helpers so scaffold and dispatch cannot drift."""
from __future__ import annotations

import re


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

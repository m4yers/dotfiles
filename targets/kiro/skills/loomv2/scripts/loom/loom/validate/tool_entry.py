"""Static tool-entry validation.

Walks every ``kind: tool`` task in the composed plan, resolves its
source folder via :func:`loom.engine.runner.task_source_folder`, and
enforces:

  (a) ``tool.py`` and ``tool.sh`` MUST NOT both be present in the
      same folder — else :class:`AmbiguousToolEntryError`.
  (b) When the entry is ``tool.sh``, the file MUST have the
      owner-execute bit set (``stat.S_IXUSR``) AND MUST start with
      the two bytes ``#!`` — else :class:`ToolShimNotExecutableError`.

Runs statically — never dispatches — so failures land before any
workdir write, preserving the nothing-written-on-init-failure
invariant. Registered by :func:`loom._lifecycle._static_validate` so
both ``$LOOM validate`` and ``$LOOM runtime init`` run this pass.
"""
from __future__ import annotations

import stat

from loom.engine.models import LoomPlan, Task
from loom.errors import AmbiguousToolEntryError, ToolShimNotExecutableError


def validate_tool_entry(plan: LoomPlan) -> None:
    """Enforce the tool-entry rules for every ``kind: tool`` task."""
    from loom.engine.runner import task_source_folder

    for t in plan.tasks:
        if not isinstance(t, Task):
            continue
        if t.kind != "tool":
            continue
        folder = task_source_folder(plan.loom_root, t)
        tool_py = folder / "tool.py"
        tool_sh = folder / "tool.sh"
        if tool_py.exists() and tool_sh.exists():
            raise AmbiguousToolEntryError(
                f"task {t.id!r}: folder {folder} contains both "
                f"tool.py and tool.sh"
            )
        if not tool_sh.exists():
            continue
        mode = tool_sh.stat().st_mode
        if not (mode & stat.S_IXUSR):
            raise ToolShimNotExecutableError(
                f"task {t.id!r}: {tool_sh} is not owner-executable"
            )
        with tool_sh.open("rb") as fh:
            head = fh.read(2)
        if head != b"#!":
            raise ToolShimNotExecutableError(
                f"task {t.id!r}: {tool_sh} does not start with a "
                f"`#!` shebang"
            )

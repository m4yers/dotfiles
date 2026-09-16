"""Ready-set computation, cascade-skip, and status transitions.

Namespaced ids from subgraph inlining are treated uniformly — the
algorithm sees only canonical addresses.
"""
from __future__ import annotations

from loom.engine.models import LoomPlan, Task


TERMINAL = {"done", "failed", "skipped"}


def status_of(plan: LoomPlan, task_id: str) -> str:
    """Return the current status of ``task_id``."""
    for t in plan.tasks:
        if isinstance(t, Task) and t.id == task_id:
            return t.status
    raise KeyError(task_id)


def ready_tasks(plan: LoomPlan) -> list[Task]:
    """Return every task ready to run right now.

    A task is ready when all deps are terminal AND its ``when``
    predicate (evaluated by the caller) has not been decided yet. This
    function only checks structural readiness; predicate evaluation
    lives in runner.py.
    """
    out: list[Task] = []
    for t in plan.tasks:
        if not isinstance(t, Task) or t.status != "pending":
            continue
        deps = list(t.depends_on_all) + list(t.depends_on_any)
        if all(status_of(plan, d) in TERMINAL for d in deps):
            out.append(t)
    return out


def cascade_skip(plan: LoomPlan, task: Task) -> bool:
    """Return True if ``task`` should be marked skipped by cascade rules.

    - depends_on_all with any skipped dep → skip (AND is False).
    - non-empty depends_on_any where every dep is skipped → skip.
    """
    if any(status_of(plan, d) == "skipped" for d in task.depends_on_all):
        return True
    if task.depends_on_any and all(
        status_of(plan, d) == "skipped" for d in task.depends_on_any
    ):
        return True
    return False


def failed_task_ids(plan: LoomPlan) -> list[str]:
    """Return every failed task id in declaration order."""
    return [t.id for t in plan.tasks if isinstance(t, Task) and t.status == "failed"]


def is_done(plan: LoomPlan) -> bool:
    """True when every task in the plan is in a terminal status."""
    return all(
        t.status in TERMINAL
        for t in plan.tasks
        if isinstance(t, Task)
    )


def is_stuck(plan: LoomPlan) -> bool:
    """True when the plan is not done and no task can make progress.

    A stuck plan has at least one non-terminal task, nothing ready or
    running, and no pending task whose deps are all terminal (so the
    ready-set would surface it).
    """
    if is_done(plan):
        return False
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    for t in tasks:
        if t.status in ("ready", "running"):
            return False
    for t in tasks:
        if t.status == "pending":
            deps = list(t.depends_on_all) + list(t.depends_on_any)
            if all(status_of(plan, d) in TERMINAL for d in deps):
                return False
    return any(t.status == "pending" for t in tasks)

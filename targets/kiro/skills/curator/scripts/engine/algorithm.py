"""DAG algorithm — ready-set, transitions, cycle detection.

Plan-only API: every function reads (and possibly mutates)
``Task.status`` directly. No separate state object.
"""
from __future__ import annotations

from engine.models import (
    Plan, Task,
    STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED,
    TERMINAL_STATUSES,
)


def validate_dag(plan: Plan) -> None:
    """Raise ValueError if the plan has duplicate ids, missing deps,
    or cycles."""
    ids = [t.id for t in plan.tasks]
    if len(ids) != len(set(ids)):
        seen = set()
        dup = next(i for i in ids if i in seen or seen.add(i))
        raise ValueError(f"duplicate task id in plan: {dup!r}")

    by_id = {t.id: t for t in plan.tasks}
    for t in plan.tasks:
        for dep in t.depends_on:
            if dep not in by_id:
                raise ValueError(
                    f"task {t.id!r} depends on unknown id {dep!r}")

    # Topological sort to detect cycles.
    visited:   dict[str, int] = {tid: 0 for tid in by_id}  # 0=white, 1=gray, 2=black
    def dfs(tid: str) -> None:
        if visited[tid] == 1:
            raise ValueError(f"cycle detected at task {tid!r}")
        if visited[tid] == 2:
            return
        visited[tid] = 1
        for dep in by_id[tid].depends_on:
            dfs(dep)
        visited[tid] = 2
    for tid in by_id:
        if visited[tid] == 0:
            dfs(tid)


def ready(plan: Plan) -> list[Task]:
    """Return tasks whose status is pending and whose dependencies
    are all done. Tasks blocked by a failed dependency stay pending
    forever (the plan reaches ``is_done`` with failed > 0)."""
    by_id = {t.id: t for t in plan.tasks}
    out: list[Task] = []
    for t in plan.tasks:
        if t.status != STATUS_PENDING:
            continue
        if all(by_id[d].status == STATUS_DONE for d in t.depends_on):
            out.append(t)
    return out


def is_done(plan: Plan) -> bool:
    """Plan terminates when every task is in a terminal status.

    Distinguish success vs partial-failure by inspecting whether any
    task has status == failed.
    """
    return all(t.status in TERMINAL_STATUSES for t in plan.tasks)


def has_failures(plan: Plan) -> bool:
    """True if any task has failed."""
    return any(t.status == STATUS_FAILED for t in plan.tasks)


# ── transitions ─────────────────────────────────────────────────


def mark_running(plan: Plan, task_ids: list[str]) -> None:
    """Move tasks to running."""
    for t in plan.tasks:
        if t.id in task_ids:
            t.status = STATUS_RUNNING


def mark_done(plan: Plan, task_id: str) -> None:
    plan.get(task_id).status = STATUS_DONE


def mark_failed(plan: Plan, task_id: str) -> None:
    plan.get(task_id).status = STATUS_FAILED


def mark_pending(plan: Plan, task_id: str) -> None:
    plan.get(task_id).status = STATUS_PENDING


def reset_task(plan: Plan, task_id: str) -> None:
    """Return a task to pending. Does NOT cascade to dependents."""
    plan.get(task_id).status = STATUS_PENDING

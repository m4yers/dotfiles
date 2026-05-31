'''DAG integrity validation: duplicate ids, missing deps, cycles.'''
from __future__ import annotations

from loom.engine.models import LoomPlan
from loom.errors import DAGError, LoomPlanError


def validate_dag(plan: LoomPlan) -> None:
    '''Raise DAGError on duplicate ids, missing deps, or cycles.'''
    ids = [t.id for t in plan.tasks]
    if len(ids) != len(set(ids)):
        seen: set[str] = set()
        for i in ids:
            if i in seen:
                raise DAGError(f'duplicate task id: {i!r}')
            seen.add(i)

    by_id = {t.id: t for t in plan.tasks}
    for t in plan.tasks:
        for dep in t.depends_on:
            if dep not in by_id:
                raise DAGError(
                    f'task {t.id!r} depends on unknown id {dep!r}')

    # cycle detection (white/gray/black DFS)
    color: dict[str, int] = {tid: 0 for tid in by_id}

    def dfs(tid: str) -> None:
        if color[tid] == 1:
            raise DAGError(f'cycle detected at task {tid!r}')
        if color[tid] == 2:
            return
        color[tid] = 1
        for dep in by_id[tid].depends_on:
            dfs(dep)
        color[tid] = 2

    for tid in by_id:
        if color[tid] == 0:
            dfs(tid)


def validate_kind_fields(plan: LoomPlan) -> None:
    '''Check that each task's per-kind fields are consistent.

    Empty dependency lists are NOT validated here — the
    ``Task`` dataclass defaults both ``depends_on_all`` and
    ``depends_on_any`` to ``[]``, making "absent" and "explicitly
    empty" indistinguishable at this point. Empty-list rejection
    is the responsibility of the factory functions in
    ``loom.plan``, where the caller's intent is observable.
    '''
    for t in plan.tasks:
        if t.kind == 'tool':
            if not t.cmd:
                raise LoomPlanError(
                    f'tool task {t.id!r}: cmd is required')
            if not t.output_schema:
                raise LoomPlanError(
                    f'tool task {t.id!r}: output_schema is required')
            if t.template is not None:
                raise LoomPlanError(
                    f'tool task {t.id!r}: template not allowed')
            if t.vars:
                raise LoomPlanError(
                    f'tool task {t.id!r}: vars not allowed')
        elif t.kind == 'agent':
            if not t.template:
                raise LoomPlanError(
                    f'agent task {t.id!r}: template is required')
            if not t.output_schema:
                raise LoomPlanError(
                    f'agent task {t.id!r}: output_schema is required')
            if t.cmd is not None:
                raise LoomPlanError(
                    f'agent task {t.id!r}: cmd not allowed')
        elif t.kind == 'human':
            if t.cmd is not None:
                raise LoomPlanError(
                    f'human task {t.id!r}: cmd not allowed')
        else:
            raise LoomPlanError(
                f'task {t.id!r}: unknown kind {t.kind!r}')

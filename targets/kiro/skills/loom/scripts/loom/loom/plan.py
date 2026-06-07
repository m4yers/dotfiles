'''Plan builder API. Skills construct LoomPlans via these factories.'''
from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

from loom.engine.models import Task, LoomPlan


_DEPRECATION_MSG = (
    'task {id!r}: depends_on= is deprecated and will be removed in a '
    'future release. Use depends_on_all= for the current "wait for all" '
    'semantics, or depends_on_any= for "wait for any one". '
    'depends_on= currently maps to depends_on_all=.'
)


def _migrate_depends_on(
    id: str,
    depends_on: list[str] | None,
    depends_on_all: list[str] | None,
    depends_on_any: list[str] | None,
) -> tuple[list[str], list[str]]:
    '''Resolve the three dep-list kwargs into ``(all, any)``.

    Emits a FutureWarning when the legacy ``depends_on`` is used.
    Raises ValueError when ``depends_on`` is mixed with the new
    ``depends_on_all`` (ambiguous — caller must pick one).
    Raises ValueError when either dependency list is supplied but
    empty (root tasks must omit the field, not pass ``[]``).
    The warning's stacklevel is 3 so the message points at the
    factory's caller (``tool('x', depends_on=...)``), not at
    this helper.
    '''
    if depends_on is not None:
        if depends_on_all is not None:
            raise ValueError(
                f'task {id!r}: depends_on (deprecated) cannot coexist '
                f'with depends_on_all; pick one'
            )
        warnings.warn(
            _DEPRECATION_MSG.format(id=id),
            FutureWarning,
            stacklevel=3,
        )
        depends_on_all = depends_on
    if depends_on_all is not None and len(depends_on_all) == 0:
        raise ValueError(
            f'task {id!r}: depends_on_all must be non-empty when '
            f'supplied; omit the field for a root task'
        )
    if depends_on_any is not None and len(depends_on_any) == 0:
        raise ValueError(
            f'task {id!r}: depends_on_any must be non-empty when '
            f'supplied; omit the field for a root task'
        )
    return list(depends_on_all or []), list(depends_on_any or [])


def latch(
    header: str,
    *,
    fuel: int | None = None,
    while_: str | None = None,
) -> dict:
    '''Build a `latch:` block for a loop task.

    `header` is the back-edge target — the loop entry. For a self-loop
    it equals the task's own id. At least one exit control must be given:
    `fuel` (a positive integer countdown, decremented each round, exit at
    0) and/or `while_` (a predicate string; the loop exits when it is
    false). Both may be combined — the loop stops as soon as either fires.

    Pass the result as the `latch=` kwarg of `tool`/`agent`/`human`.
    '''
    block: dict[str, Any] = {'header': header}
    if fuel is not None:
        block['fuel'] = fuel
    if while_ is not None:
        block['while'] = while_
    return block


def tool(
    id: str,
    *,
    cmd: list[str],
    output_schema: str | Path,
    depends_on: list[str] | None = None,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    latch: dict | None = None,
) -> Task:
    '''Build a tool kind Task.

    Use ``depends_on_all=`` for "wait for every listed task to reach
    a terminal status" (the default semantics; this is what the old
    ``depends_on=`` did). Use ``depends_on_any=`` for "wait for at
    least one listed task to reach a terminal status". Both lists
    can be combined on a single task.
    '''
    if cmd is None or len(cmd) == 0:
        raise ValueError(f'tool task {id!r}: cmd is required and must be non-empty')
    if output_schema is None:
        raise ValueError(f'tool task {id!r}: output_schema is required')
    da, dy = _migrate_depends_on(id, depends_on, depends_on_all, depends_on_any)
    return Task(
        id=id,
        kind='tool',
        cmd=list(cmd),
        output_schema=str(output_schema),
        depends_on_all=da,
        depends_on_any=dy,
        when=when,
        latch=dict(latch) if latch else None,
    )


def agent(
    id: str,
    *,
    template: str | Path,
    output_schema: str | Path,
    depends_on: list[str] | None = None,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    vars: dict[str, Any] | None = None,
    agent: str | None = None,
    template_search_paths: list[str | Path] | None = None,
    latch: dict | None = None,
) -> Task:
    '''Build an agent kind Task.

    See ``tool`` for dependency semantics.
    '''
    if template is None:
        raise ValueError(f'agent task {id!r}: template is required')
    if output_schema is None:
        raise ValueError(f'agent task {id!r}: output_schema is required')
    da, dy = _migrate_depends_on(id, depends_on, depends_on_all, depends_on_any)
    return Task(
        id=id,
        kind='agent',
        template=str(template),
        output_schema=str(output_schema),
        agent=agent,
        vars=dict(vars or {}),
        depends_on_all=da,
        depends_on_any=dy,
        when=when,
        template_search_paths=(
            [str(p) for p in template_search_paths]
            if template_search_paths is not None else None
        ),
        latch=dict(latch) if latch else None,
    )


def human(
    id: str,
    *,
    template: str | Path | None = None,
    output_schema: str | Path | None = None,
    depends_on: list[str] | None = None,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    vars: dict[str, Any] | None = None,
    template_search_paths: list[str | Path] | None = None,
    latch: dict | None = None,
) -> Task:
    '''Build a human kind Task.

    See ``tool`` for dependency semantics.
    '''
    da, dy = _migrate_depends_on(id, depends_on, depends_on_all, depends_on_any)
    return Task(
        id=id,
        kind='human',
        template=str(template) if template is not None else None,
        output_schema=str(output_schema) if output_schema is not None else None,
        vars=dict(vars or {}),
        depends_on_all=da,
        depends_on_any=dy,
        when=when,
        template_search_paths=(
            [str(p) for p in template_search_paths]
            if template_search_paths is not None else None
        ),
        latch=dict(latch) if latch else None,
    )


def make_plan(*tasks: Task) -> LoomPlan:
    '''Assemble a LoomPlan from Task instances.'''
    return LoomPlan(tasks=list(tasks))

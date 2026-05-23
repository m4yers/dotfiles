'''Plan builder API. Skills construct LoomPlans via these factories.'''
from __future__ import annotations

from pathlib import Path
from typing import Any

from loom.engine.models import Task, LoomPlan


def tool(
    id: str,
    *,
    cmd: list[str],
    output_schema: str | Path,
    depends_on: list[str] | None = None,
    when: str | None = None,
) -> Task:
    '''Build a tool kind Task.'''
    if cmd is None or len(cmd) == 0:
        raise ValueError(f'tool task {id!r}: cmd is required and must be non-empty')
    if output_schema is None:
        raise ValueError(f'tool task {id!r}: output_schema is required')
    return Task(
        id=id,
        kind='tool',
        cmd=list(cmd),
        output_schema=str(output_schema),
        depends_on=list(depends_on or []),
        when=when,
    )


def agent(
    id: str,
    *,
    template: str | Path,
    output_schema: str | Path,
    depends_on: list[str] | None = None,
    when: str | None = None,
    vars: dict[str, Any] | None = None,
    agent: str | None = None,
) -> Task:
    '''Build an agent kind Task.'''
    if template is None:
        raise ValueError(f'agent task {id!r}: template is required')
    if output_schema is None:
        raise ValueError(f'agent task {id!r}: output_schema is required')
    return Task(
        id=id,
        kind='agent',
        template=str(template),
        output_schema=str(output_schema),
        agent=agent,
        vars=dict(vars or {}),
        depends_on=list(depends_on or []),
        when=when,
    )


def human(
    id: str,
    *,
    template: str | Path | None = None,
    output_schema: str | Path | None = None,
    depends_on: list[str] | None = None,
    when: str | None = None,
    vars: dict[str, Any] | None = None,
) -> Task:
    '''Build a human kind Task.'''
    return Task(
        id=id,
        kind='human',
        template=str(template) if template is not None else None,
        output_schema=str(output_schema) if output_schema is not None else None,
        vars=dict(vars or {}),
        depends_on=list(depends_on or []),
        when=when,
    )


def make_plan(*tasks: Task) -> LoomPlan:
    '''Assemble a LoomPlan from Task instances.'''
    return LoomPlan(tasks=list(tasks))

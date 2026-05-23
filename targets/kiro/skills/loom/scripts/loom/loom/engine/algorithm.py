'''Plan algorithm: predicate desugaring + ready-set + transitions.

This module contains pure functions; runtime methods live in runner.py.
'''
from __future__ import annotations

import re
from pathlib import Path

import jmespath
import yaml

from loom.engine.models import (
    LoomPlan, Task,
    STATUS_PENDING, STATUS_READY, STATUS_RUNNING,
    STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED,
    TERMINAL_STATUSES,
)

# Matches ${task:<id>:<path>} or ${task:<id>}
_TASK_REF_RE = re.compile(
    r'\$\{task:([A-Za-z0-9_\-]+)(?::([^}]+))?\}')


def desugar_predicate(expr: str) -> str:
    '''Convert ${task:id:path} sugar to JMESPath: task."id".path'''
    def repl(m: re.Match) -> str:
        tid = m.group(1)
        path = m.group(2)
        if path:
            return f'task."{tid}".{path}'
        return f'task."{tid}"'
    return _TASK_REF_RE.sub(repl, expr)


def all_deps_terminal(task: Task, plan: LoomPlan) -> bool:
    by_id = {t.id: t for t in plan.tasks}
    for dep in task.depends_on:
        if dep not in by_id:
            return False
        if by_id[dep].status not in TERMINAL_STATUSES:
            return False
    return True


def compute_ready_set(plan: LoomPlan) -> list[Task]:
    '''Tasks in pending or ready status whose deps are all terminal.'''
    out = []
    for t in plan.tasks:
        if t.status not in (STATUS_PENDING, STATUS_READY):
            continue
        if all_deps_terminal(t, plan):
            out.append(t)
    return out


def is_done(plan: LoomPlan) -> bool:
    return all(t.status in TERMINAL_STATUSES for t in plan.tasks)


def is_stuck(plan: LoomPlan) -> bool:
    '''Some tasks are non-terminal, but none can progress.'''
    if is_done(plan):
        return False
    for t in plan.tasks:
        if t.status in (STATUS_READY, STATUS_RUNNING):
            return False
    for t in plan.tasks:
        if t.status == STATUS_PENDING and all_deps_terminal(t, plan):
            return False
    return any(t.status == STATUS_PENDING for t in plan.tasks)


# ---- predicate evaluation ----

def build_predicate_context(plan: LoomPlan, workdir: Path) -> dict:
    '''Virtual document {task: {<id>: <output_or_none>, ...}} for predicate eval.'''
    from loom.engine import store
    task_outputs = {}
    for t in plan.tasks:
        try:
            tp = store.task_output_path(workdir, plan, t.id)
        except KeyError:
            tp = None
        if tp and tp.exists():
            try:
                task_outputs[t.id] = yaml.safe_load(tp.read_text(encoding='utf-8'))
            except Exception:
                task_outputs[t.id] = None
        else:
            task_outputs[t.id] = None
    return {'task': task_outputs}


def eval_predicate(when_expr: str, plan: LoomPlan, workdir: Path) -> tuple[bool, str | None]:
    '''Returns (truthy, reason). truthy=True means runnable.'''
    if not when_expr:
        return True, None
    desugared = desugar_predicate(when_expr)
    ctx = build_predicate_context(plan, workdir)
    try:
        result = jmespath.search(desugared, ctx)
    except Exception as e:
        return False, f'predicate-error: {e}'
    if result:
        return True, None
    return False, f'when-false: {when_expr!r}'


def partition_ready(
    candidates: list[Task],
    plan: LoomPlan,
    workdir: Path,
) -> tuple[list[Task], list[tuple[Task, str]]]:
    '''Split candidates by predicate evaluation.'''
    runnable = []
    skipped = []
    for t in candidates:
        ok, reason = eval_predicate(t.when, plan, workdir)
        if ok:
            runnable.append(t)
        else:
            skipped.append((t, reason or 'when-false'))
    return runnable, skipped


def mark_status(task: Task, new: str) -> None:
    task.status = new

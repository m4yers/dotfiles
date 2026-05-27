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
    '''True when the task's dependency conditions are satisfied.

    Conditions:
      - Every id in ``depends_on_all`` is in a terminal status, AND
      - if ``depends_on_any`` is non-empty, at least one of its
        ids is in a terminal status.

    Missing ids count as not-terminal — a dangling reference
    blocks readiness rather than crashing the scheduler. Static
    validation in ``loom.init`` catches missing ids before any
    plan reaches this function in normal use.

    The function name is preserved for back-compat with callers
    that imported it; the body now spans both dep lists.
    '''
    by_id = {t.id: t for t in plan.tasks}

    # All-list: every dep must be terminal.
    for dep in task.depends_on_all:
        if dep not in by_id:
            return False
        if by_id[dep].status not in TERMINAL_STATUSES:
            return False

    # Any-list (when present): at least one dep must be terminal.
    if task.depends_on_any:
        any_ok = False
        for dep in task.depends_on_any:
            if dep not in by_id:
                continue
            if by_id[dep].status in TERMINAL_STATUSES:
                any_ok = True
                break
        if not any_ok:
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
    '''Split candidates by predicate evaluation and cascade-skip.'''
    by_id = {t.id: t for t in plan.tasks}
    runnable: list[Task] = []
    skipped: list[tuple[Task, str]] = []
    for t in candidates:
        ok, reason = eval_predicate(t.when, plan, workdir)
        if not ok:
            skipped.append((t, reason or 'when-false'))
            continue
        # Cascade skip — the task has nothing to consume because
        # an entire dep list was skipped:
        #   - depends_on_all all skipped → no "all" upstream output.
        #   - depends_on_any all skipped → no "any" upstream output.
        # Either condition independently triggers cascade. The
        # all-list rule is identical to pre-fork loom behavior.
        cascade_reason = _cascade_reason(t, by_id)
        if cascade_reason is not None:
            skipped.append((t, cascade_reason))
            continue
        runnable.append(t)
    return runnable, skipped


def _cascade_reason(task: Task, by_id: dict[str, Task]) -> str | None:
    '''Return a human-readable cascade reason if the task should
    be auto-skipped because an entire dep list was skipped, else
    None.'''
    da = [d for d in task.depends_on_all if d in by_id]
    if da and all(by_id[d].status == STATUS_SKIPPED for d in da):
        return f'cascade: all {len(da)} all-deps skipped'
    dy = [d for d in task.depends_on_any if d in by_id]
    if dy and all(by_id[d].status == STATUS_SKIPPED for d in dy):
        return f'cascade: all {len(dy)} any-deps skipped'
    return None


def mark_status(task: Task, new: str) -> None:
    task.status = new

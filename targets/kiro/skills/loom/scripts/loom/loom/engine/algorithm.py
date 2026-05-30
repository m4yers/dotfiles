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
    '''True when every referenced dep has reached a terminal status.

    Predicate evaluation (and the failure-cascade decision) is
    deferred until ALL deps in either list are terminal. A
    missing id counts as undecided so the scheduler waits rather
    than crashes; static validation in ``loom.init`` catches
    truly dangling references before any plan reaches this
    function.
    '''
    by_id = {t.id: t for t in plan.tasks}
    for dep in list(task.depends_on_all) + list(task.depends_on_any):
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
) -> tuple[list[Task], list[tuple[Task, str]], list[tuple[Task, str]]]:
    '''Split candidates by failure cascade and predicate evaluation.

    Returns three buckets:

    * ``runnable`` — task can be dispatched.
    * ``skipped``  — task's ``when:`` predicate evaluated false;
      this is a successful terminal (the task simply doesn't
      apply).
    * ``failed``   — at least one upstream cascaded a failure;
      the task itself fails immediately.

    Resolution order, per task:

    1. Cascade-fail check. ``depends_on_all`` cascades on any
       failed dep; ``depends_on_any`` cascades only when every
       dep failed (a single failure is tolerable when there are
       alternatives).
    2. Predicate (``when:``). If false, mark skipped.
    3. Otherwise, runnable.

    Skipped (``when:``-false) deps do NOT cascade — they count
    as a non-failure terminal, equivalent to ``done`` for
    predicate purposes. Failure is the only contagious status.
    '''
    by_id = {t.id: t for t in plan.tasks}
    runnable: list[Task] = []
    skipped: list[tuple[Task, str]] = []
    failed: list[tuple[Task, str]] = []
    for t in candidates:
        fail_reason = _cascade_fail_reason(t, by_id)
        if fail_reason is not None:
            failed.append((t, fail_reason))
            continue
        ok, reason = eval_predicate(t.when, plan, workdir)
        if not ok:
            skipped.append((t, reason or 'when-false'))
            continue
        runnable.append(t)
    return runnable, skipped, failed


def _cascade_fail_reason(task: Task, by_id: dict[str, Task]) -> str | None:
    '''Return a human-readable cascade-fail reason if upstream
    failures should propagate as a failure of this task, else
    None.

    Rules:
      - ``depends_on_all``: any dep is ``failed`` → fail.
      - ``depends_on_any``: every present dep is ``failed`` →
        fail (no alternative path remains).
    Skipped deps are non-failures and do not contribute.
    '''
    da = [d for d in task.depends_on_all if d in by_id]
    bad_all = [d for d in da if by_id[d].status == STATUS_FAILED]
    if bad_all:
        first = bad_all[0]
        return (f'cascade-fail: {len(bad_all)}/{len(da)} all-deps failed '
                f'(first: {first})')
    dy = [d for d in task.depends_on_any if d in by_id]
    if dy and all(by_id[d].status == STATUS_FAILED for d in dy):
        return f'cascade-fail: all {len(dy)} any-deps failed'
    return None


def mark_status(task: Task, new: str) -> None:
    task.status = new

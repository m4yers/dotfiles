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

# Matches ${task:<id>:<path>} or ${task:<id>}.
# The (?<!\$) negative lookbehind mirrors _PLACEHOLDER_RE in
# loom/engine/resolve.py: a leading $$ escapes the placeholder
# so it is not seen as a reference. Without this, validators
# that share this regex would reject literal $${task:...}
# strings in user-supplied vars even though the resolver
# correctly turns them into a literal ${task:...} at render
# time.
_TASK_REF_RE = re.compile(
    r'(?<!\$)\$\{task:([A-Za-z0-9_\-]+)(?::([^}]+))?\}')


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
    '''Split candidates into runnable and skipped buckets.

    Returns three buckets for backward-compatibility with callers
    that destructure as ``runnable, skipped, failed``:

    * ``runnable`` — task can be dispatched.
    * ``skipped``  — task is skipped; reason is one of:

      - cascade-skip: an upstream dep in ``depends_on_all`` is
        ``skipped`` (AND with False is False); or every dep in a
        non-empty ``depends_on_any`` is ``skipped`` (OR with all
        Falses is False);
      - when-false: the task's own ``when:`` predicate evaluated
        false.

    * ``failed``   — always empty. Failure is no longer cascaded
      through the DAG; ``failed`` deps abort the entire run via
      ``LoomRuntime.next()`` raising ``RunAborted``. The third
      return value is preserved as ``[]`` so existing callers
      continue to work.

    Resolution order, per task:

    1. Cascade-skip check. ``depends_on_all`` skips on any
       skipped dep (AND); ``depends_on_any`` skips when every
       present dep is skipped (OR).
    2. Predicate (``when:``). If false, mark skipped.
    3. Otherwise, runnable.

    Logical model: ``done`` ≡ True, ``skipped`` ≡ False,
    ``depends_on_all`` ≡ AND, ``depends_on_any`` ≡ OR. Failure
    is not a logical state — it is an exceptional condition that
    aborts the run; this function never sees a ``failed`` dep
    because the runner intercepts failures before scheduling
    resumes.
    '''
    by_id = {t.id: t for t in plan.tasks}
    runnable: list[Task] = []
    skipped: list[tuple[Task, str]] = []
    for t in candidates:
        skip_reason = _cascade_skip_reason(t, by_id)
        if skip_reason is not None:
            skipped.append((t, skip_reason))
            continue
        ok, reason = eval_predicate(t.when, plan, workdir)
        if not ok:
            skipped.append((t, reason or 'when-false'))
            continue
        runnable.append(t)
    return runnable, skipped, []


def _cascade_skip_reason(task: Task, by_id: dict[str, Task]) -> str | None:
    '''Return a human-readable cascade-skip reason if upstream
    skips should propagate as a skip of this task, else None.

    Rules (logical model: skipped = False, done = True):
      - ``depends_on_all`` is AND: any dep is ``skipped`` → skip
        (False makes the conjunction False).
      - ``depends_on_any`` is OR: every dep is ``skipped`` → skip
        (all Falses make the disjunction False).
    '''
    da = [d for d in task.depends_on_all if d in by_id]
    skipped_in_all = [d for d in da if by_id[d].status == STATUS_SKIPPED]
    if skipped_in_all:
        first = skipped_in_all[0]
        return (f'cascade-skip: {len(skipped_in_all)}/{len(da)} all-deps '
                f'skipped (first: {first})')
    dy = [d for d in task.depends_on_any if d in by_id]
    if dy and all(by_id[d].status == STATUS_SKIPPED for d in dy):
        return f'cascade-skip: all {len(dy)} any-deps skipped'
    return None


def find_failed_tasks(plan: LoomPlan) -> list[str]:
    '''Return ids of tasks in ``failed`` status, in plan order.

    Used by ``LoomRuntime.next()`` to decide whether the run
    has been aborted by a prior failure.
    '''
    return [t.id for t in plan.tasks if t.status == STATUS_FAILED]


def mark_status(task: Task, new: str) -> None:
    task.status = new

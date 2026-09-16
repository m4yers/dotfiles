"""Runtime predicate evaluation: ``${task:...}`` sugar → JMESPath.

Port of the v1 machinery, adapted to v2 canonical addresses (which may
contain ``/`` from subgraph inlining — hence quoted JMESPath keys) and
the v2 store layout (flat ``output.yaml`` for plain tasks, ``iter-NN/``
round dirs for loop-body tasks).

Used by ``loops.latch_continue`` for ``while_`` exit controls. Pure
reads: nothing here mutates plan or disk.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import jmespath
import yaml

from loom.engine.models import LoomPlan, Task

# Matches ${task:<addr>}, ${task:<addr>:<path>}, ${task:<addr>@<sel>},
# ${task:<addr>@<sel>:<path>}. <addr> is a canonical address (may
# contain '/'); <sel> is an absolute round index or 'prev'. The
# (?<!\$) lookbehind skips the $${...} escape form.
_TASK_REF_RE = re.compile(
    r"(?<!\$)\$\{task:([A-Za-z0-9_\-/]+)(?:@([A-Za-z0-9]+))?(?::([^}]+))?\}"
)


def desugar_predicate(expr: str) -> str:
    """Convert ``${task:addr:path}`` sugar to JMESPath: ``task."addr".path``.

    An iteration selector ``${task:addr@sel:path}`` desugars to
    ``task_iter."addr"."sel".path``, resolved against the per-round
    document built in :func:`build_predicate_context`.
    """
    def repl(m: re.Match) -> str:
        addr = m.group(1)
        sel = m.group(2)
        path = m.group(3)
        if sel is not None:
            # Normalise a numeric selector so it matches the str(int)
            # keys in the task_iter document (e.g. @05 -> "5").
            if sel.isdigit():
                sel = str(int(sel))
            base = f'task_iter."{addr}"."{sel}"'
        else:
            base = f'task."{addr}"'
        return f"{base}.{path}" if path else base

    return _TASK_REF_RE.sub(repl, expr)


def build_predicate_context(
    plan: LoomPlan,
    workdir: Path,
    evaluator: tuple[str, int | None] | None = None,
) -> dict:
    """Virtual document for predicate eval.

    ``task`` maps each id to its latest-completed output (or None).
    ``task_iter`` maps each loop-body id to a dict keyed by round index
    (as a string) plus ``prev``, enabling ``${task:addr@sel:path}``
    references.

    ``prev`` is EVALUATOR-RELATIVE — "the most recent result produced
    before the current evaluation point":

    - ``evaluator=(id, k)`` with a round index ``k`` (a loop task
      dispatching round k, or a latch whose just-completed round is k):
      ``prev`` of any loop task is its round ``k-1`` output — ``None``
      on the very first iteration (k == 0). Loop-region rounds are
      aligned, so this reads "the previous iteration's result" and, for
      a latch reading itself, "the round before the one that just
      finished".
    - ``evaluator=(id, None)`` (a non-iterating task, e.g. reading a
      finished loop from outside): ``prev`` is the latest completed
      round — the loop's final result.
    - ``evaluator=None`` (legacy callers): the round before the latest
      completed, absent unless two rounds completed.
    """
    from loom.engine import store
    from loom.engine.loops import region_members

    loop_ids = region_members(plan)
    ev_round = evaluator[1] if evaluator is not None else None

    task_outputs: dict[str, Any] = {}
    task_iter: dict[str, Any] = {}
    for t in plan.tasks:
        if not isinstance(t, Task):
            continue
        folder = store.task_folder(workdir, plan, t.id)
        read_path = store.output_read_path(folder, is_loop_body=t.id in loop_ids)
        task_outputs[t.id] = _load(read_path)
        if t.id not in loop_ids:
            continue
        completed = store.completed_iter_indices(folder)
        per: dict[str, Any] = {
            str(i): _load(folder / f"iter-{i:02d}" / "output.yaml")
            for i in completed
        }
        if evaluator is not None:
            if ev_round is not None:
                # Previous iteration relative to the evaluator's round;
                # None on the first iteration (k-1 < 0).
                per["prev"] = per.get(str(ev_round - 1)) if ev_round > 0 else None
            elif completed:
                # Non-iterating evaluator: the loop's final result.
                per["prev"] = per[str(completed[-1])]
        elif len(completed) >= 2:
            per["prev"] = per.get(str(completed[-2]))
        if per:
            task_iter[t.id] = per

    return {"task": task_outputs, "task_iter": task_iter}


def eval_predicate(
    expr: str,
    plan: LoomPlan,
    workdir: Path,
    evaluator: tuple[str, int | None] | None = None,
) -> tuple[bool, str | None]:
    """Evaluate ``expr``. Returns ``(truthy, reason)``; reason on falsy.

    Raises :class:`PredicateEvalError` on parse errors, JMESPath
    failures, or refs that cannot be resolved. Only a clean boolean
    false skips a task or stops a loop; broken predicates halt the run
    loudly rather than being coerced to falsy.
    """
    from loom.errors import PredicateEvalError

    if not expr:
        return True, None
    desugared = desugar_predicate(expr)
    ctx = build_predicate_context(plan, workdir, evaluator)
    try:
        result = jmespath.search(desugared, ctx)
    except Exception as exc:  # noqa: BLE001 — surfaced as PredicateEvalError
        raise PredicateEvalError(expr, str(exc)) from exc
    if result:
        return True, None
    return False, f"predicate-false: {expr!r}"


def _load(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text())
    except Exception:  # noqa: BLE001 — unreadable output counts as absent
        return None

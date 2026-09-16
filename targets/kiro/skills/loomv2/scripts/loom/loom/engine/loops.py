"""Dominators, natural-loop computation, and loop region derivation.

Runs on the composed (post-inlining) plan so subgraph-hosted loops
inherit the same admission rules. Also hosts the runtime loop-control
decision (``latch_continue``) used by LoomRuntime after a latch
completes.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from loom.engine.models import LoomPlan, Task


def find_entry(plan: LoomPlan) -> str | None:
    """Return the single entry task id (no deps), or None if ambiguous."""
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    ids = {t.id for t in tasks}
    incoming: dict[str, int] = {t.id: 0 for t in tasks}
    for t in tasks:
        for d in list(t.depends_on_all) + list(t.depends_on_any):
            if d in ids:
                incoming[t.id] += 1
    entries = [i for i, c in incoming.items() if c == 0]
    return entries[0] if len(entries) == 1 else None


def loop_regions(plan: LoomPlan) -> dict[str, set[str]]:
    """Return ``latch_id → natural-loop body`` for every latch in the plan."""
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    latches = [t for t in tasks if t.latch is not None]
    if not latches:
        return {}
    entry = find_entry(plan)
    if entry is None:
        return {}
    dom = compute_dominators(plan, entry)
    return {
        t.id: natural_loop_body(plan, t.latch.header, t.id, dom)
        for t in latches
    }


def region_members(plan: LoomPlan) -> set[str]:
    """Union of all loop bodies — every task that iterates per round."""
    out: set[str] = set()
    for body in loop_regions(plan).values():
        out |= body
    return out


def latch_continue(
    latch_task: Task,
    plan: LoomPlan,
    workdir: Path,
) -> tuple[bool, int | None]:
    """Decide whether a just-completed loop should run another round.

    Returns ``(should_continue, new_fuel)``. The loop continues iff
    ``(fuel absent or fuel-1 > 0) and (while_ absent or while_ is
    true)`` — it stops as soon as either control fires. ``new_fuel`` is
    the decremented fuel (or ``None`` when no fuel is configured); the
    caller persists it on the latch. Pure: mutates nothing.

    ``while_`` is evaluated against the latest completed outputs (the
    round that just finished) via the predicate machinery; ``@prev``
    refs inside it resolve relative to the latch's just-completed
    round (its round N-1).
    """
    from loom.engine import store
    from loom.engine.predicate import eval_predicate

    latch = latch_task.latch
    while_ok = True
    if latch.while_:
        completed = store.completed_iter_indices(
            store.task_folder(Path(workdir), plan, latch_task.id)
        )
        evaluator = (latch_task.id, completed[-1] if completed else None)
        while_ok, _reason = eval_predicate(
            latch.while_, plan, workdir, evaluator=evaluator
        )

    new_fuel = latch.fuel
    fuel_ok = True
    if latch.fuel is not None:
        new_fuel = latch.fuel - 1
        fuel_ok = new_fuel > 0

    return (while_ok and fuel_ok), new_fuel


def compute_dominators(plan: LoomPlan, entry: str) -> dict[str, set[str]]:
    """Return dominator sets keyed by task id.

    Iterative fixed-point. ``entry`` is the single-entry task id.
    """
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    ids = [t.id for t in tasks]
    preds: dict[str, set[str]] = defaultdict(set)
    for t in tasks:
        for d in list(t.depends_on_all) + list(t.depends_on_any):
            preds[t.id].add(d)

    dom: dict[str, set[str]] = {i: set(ids) for i in ids}
    dom[entry] = {entry}
    changed = True
    while changed:
        changed = False
        for i in ids:
            if i == entry:
                continue
            if not preds[i]:
                new = {i}
            else:
                new = set.intersection(*(dom[p] for p in preds[i])) | {i}
            if new != dom[i]:
                dom[i] = new
                changed = True
    return dom


def natural_loop_body(plan: LoomPlan, header: str, latch: str,
                      dom: dict[str, set[str]]) -> set[str]:
    """Return the natural-loop body for back-edge ``latch -> header``.

    Includes header, latch, and every node on paths from header to latch.
    """
    if header not in dom.get(latch, set()):
        # Not reducible; caller will surface IrreducibleLoopError.
        return set()
    body: set[str] = {header, latch}
    # Standard natural-loop walk: never expand a node already in the
    # body. For a self-loop (header == latch) the latch is pre-seeded,
    # so nothing is pushed and the body is just the latch — scanning
    # the latch's preds there would wrongly pull upstream tasks in.
    stack = [latch] if latch != header else []
    tasks = {t.id: t for t in plan.tasks if isinstance(t, Task)}
    preds: dict[str, set[str]] = defaultdict(set)
    for t in tasks.values():
        for d in list(t.depends_on_all) + list(t.depends_on_any):
            preds[t.id].add(d)
    while stack:
        n = stack.pop()
        for p in preds[n]:
            if p not in body:
                body.add(p)
                stack.append(p)
    return body

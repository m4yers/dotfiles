"""Loop admission rules:

  1. Reducible — the header dominates the latch; each header has at
     most one back-edge into it.
  2. Hammock — every inflow to the loop region enters via the header;
     every outflow leaves via the latch.
  3. No overlap — loop bodies are pairwise disjoint or wholly nested.

Each raise-site formats a message of the form
``<rule>. Fix: <edit>``, so the rule text is guaranteed present in
the error surface. Test suite asserts these messages verbatim.
"""
from __future__ import annotations

from loom.engine.loops import compute_dominators, natural_loop_body
from loom.engine.models import LoomPlan, Task
from loom.errors import (
    IrreducibleLoopError,
    LoopEscapeError,
    LoopNestingError,
    NoExitConditionError,
)


def validate_loops(plan: LoomPlan) -> None:
    """Enforce the three loop admission rules."""
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    latches = [t for t in tasks if t.latch is not None]
    if not latches:
        return

    for latch_task in latches:
        if latch_task.latch.fuel is None and latch_task.latch.while_ is None:
            raise NoExitConditionError(
                f"loop latch {latch_task.id!r} has no exit control. "
                "Fix: supply fuel or while_ on the latch."
            )

    # Reducibility: header must dominate latch.
    entry = _find_entry(tasks)
    if entry is None:
        return
    dom = compute_dominators(plan, entry)
    header_count: dict[str, int] = {}
    for latch_task in latches:
        header = latch_task.latch.header
        header_count[header] = header_count.get(header, 0) + 1
        if header not in dom.get(latch_task.id, set()):
            raise IrreducibleLoopError(
                f"loop {latch_task.id!r} → {header!r}: header does not "
                "dominate latch. Fix: rewrite so the header dominates "
                "the latch, or remove the back-edge."
            )
    for header, n in header_count.items():
        if n > 1:
            raise IrreducibleLoopError(
                f"header {header!r} has {n} latches. Fix: at most one "
                "back-edge per header."
            )

    # Hammock + overlap.
    bodies = [
        (t, natural_loop_body(plan, t.latch.header, t.id, dom))
        for t in latches
    ]
    _check_hammock(plan, bodies)
    _check_overlap(bodies)


def _find_entry(tasks: list[Task]) -> str | None:
    ids = {t.id for t in tasks}
    incoming: dict[str, int] = {t.id: 0 for t in tasks}
    for t in tasks:
        for d in list(t.depends_on_all) + list(t.depends_on_any):
            if d in ids:
                incoming[t.id] += 1
    entries = [i for i, c in incoming.items() if c == 0]
    return entries[0] if len(entries) == 1 else None


def _check_hammock(plan: LoomPlan, bodies: list[tuple[Task, set[str]]]) -> None:
    tasks = {t.id: t for t in plan.tasks if isinstance(t, Task)}
    for latch_task, body in bodies:
        header = latch_task.latch.header
        for node in body:
            for d in list(tasks[node].depends_on_all) + list(tasks[node].depends_on_any):
                if d not in body and node != header:
                    raise LoopEscapeError(
                        f"edge {d!r} → {node!r} enters loop body outside "
                        f"header {header!r}. Fix: route all inflow through "
                        "the header."
                    )
        for other_id, other in tasks.items():
            if other_id in body:
                continue
            for d in list(other.depends_on_all) + list(other.depends_on_any):
                if d in body and d != latch_task.id:
                    raise LoopEscapeError(
                        f"edge {d!r} → {other_id!r} leaves loop body outside "
                        f"latch {latch_task.id!r}. Fix: route all outflow "
                        "through the latch."
                    )


def _check_overlap(bodies: list[tuple[Task, set[str]]]) -> None:
    for i, (la, ba) in enumerate(bodies):
        for lb, bb in bodies[i + 1:]:
            if ba & bb and not (ba <= bb or bb <= ba):
                raise LoopNestingError(
                    f"loops {la.id!r} and {lb.id!r} overlap without proper "
                    "nesting. Fix: make bodies disjoint or wholly nested."
                )

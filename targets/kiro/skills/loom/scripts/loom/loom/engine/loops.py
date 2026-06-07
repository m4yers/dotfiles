'''Loop-region graph analysis: dominators, natural loops, membership.

Pure functions over a LoomPlan's dependency graph. A loop is declared by a
`latch` block (header + exit controls) on the latch task; the back-edge is
``latch -> header`` and is *not* a dependency edge. The region (body) is the
natural loop of that back-edge — computed here, never hand-declared.

Edge convention: a dependency ``v depends_on u`` is a forward edge ``u -> v``
(data flows u to v). Predecessors of a node are therefore its dependencies.

Imports only the data models, so both `store` and the validators can import
this without a cycle.
'''
from __future__ import annotations

from loom.engine.models import LoomPlan, Task


def predecessors(plan: LoomPlan) -> dict[str, set[str]]:
    '''Map each task id to its dependency ids (its CFG predecessors).'''
    return {t.id: set(t.depends_on) for t in plan.tasks}


def dominators(plan: LoomPlan) -> dict[str, set[str]]:
    '''Standard iterative dominator sets over the dependency graph.

    A root (no dependencies) is dominated only by itself. ``h`` dominates
    ``n`` iff ``h in dominators(plan)[n]``.
    '''
    ids = [t.id for t in plan.tasks]
    preds = predecessors(plan)
    id_set = set(ids)
    roots = [i for i in ids if not preds.get(i)]

    dom: dict[str, set[str]] = {i: set(id_set) for i in ids}
    for r in roots:
        dom[r] = {r}

    changed = True
    while changed:
        changed = False
        for i in ids:
            if i in roots:
                continue
            new = set(id_set)
            for p in preds.get(i, ()):
                if p in dom:
                    new &= dom[p]
            new = {i} | new
            if new != dom[i]:
                dom[i] = new
                changed = True
    return dom


def natural_loop(plan: LoomPlan, header: str, latch: str) -> set[str]:
    '''Body of the natural loop for back-edge ``latch -> header``.

    Returns ``{header}`` plus every node from which ``latch`` is reachable
    without passing through ``header`` (Appel's algorithm). For a self-loop
    (``header == latch``) the body is just ``{header}``.
    '''
    preds = predecessors(plan)
    loop = {header}
    stack: list[str] = []
    if latch not in loop:
        loop.add(latch)
        stack.append(latch)
    while stack:
        m = stack.pop()
        for p in preds.get(m, ()):
            if p not in loop:
                loop.add(p)
                stack.append(p)
    return loop


def latch_tasks(plan: LoomPlan) -> list[Task]:
    '''Tasks carrying a `latch` block, in plan order.'''
    return [t for t in plan.tasks if getattr(t, 'latch', None)]


def all_regions(plan: LoomPlan) -> dict[str, set[str]]:
    '''Map each latch id to its region body (natural loop).'''
    out: dict[str, set[str]] = {}
    for t in latch_tasks(plan):
        header = (t.latch or {}).get('header')
        if header is None:
            continue
        out[t.id] = natural_loop(plan, header, t.id)
    return out


def region_members(plan: LoomPlan) -> set[str]:
    '''Union of all loop region bodies — every task with loop semantics.'''
    members: set[str] = set()
    for body in all_regions(plan).values():
        members |= body
    return members


def region_containing(plan: LoomPlan, task_id: str) -> set[str]:
    '''Union of all region bodies that contain ``task_id`` (empty if the
    task is in no loop). Used to reset a whole region together.'''
    out: set[str] = set()
    for body in all_regions(plan).values():
        if task_id in body:
            out |= body
    return out

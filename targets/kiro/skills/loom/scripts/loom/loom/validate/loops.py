'''Loop-admission validation.

A task carrying a ``latch`` block declares a loop with back-edge
``latch -> header``. This pass admits only **reducible** loops whose region
is a **hammock** (single-entry / single-exit), so the region collapses to a
super-node and the rest of the plan stays a DAG.

Checks (raise a LoopError / DAGError subclass; nothing is written on
failure):
  - ``latch.header`` present and names a real task.
  - At least one exit control (``fuel`` / ``while``) — ``NoExitConditionError``.
    This is the only exit check; it is *not* a termination proof (a huge
    ``fuel`` "terminates" but never ends in practice).
  - ``fuel``, if present, is a positive integer.
  - Reducibility (C3): ``header`` dominates ``latch``; at most one latch per
    header.
  - Region (C4): the body is the *derived* natural loop — never declared.
  - Hammock (C1/C2): every edge (dependency or ${task:...} reference) that
    crosses the region boundary enters through the header or leaves through
    the latch.
  - Nesting (C5): regions are disjoint or properly nested.
'''
from __future__ import annotations

from loom.engine.models import LoomPlan, Task
from loom.engine import loops
from loom.engine.algorithm import _TASK_REF_RE
from loom.errors import (
    DAGError, LoomPlanError, NoExitConditionError,
    IrreducibleLoopError, LoopEscapeError, LoopNestingError,
)
import re

# ${task_path:<id>} references are data edges too (the design's boundary
# scan covers every reference form, not just ${task:...}).
_TASK_PATH_RE = re.compile(r'(?<!\$)\$\{task_path:([A-Za-z0-9_\-]+)')


def _ref_ids(s) -> list[str]:
    if not isinstance(s, str):
        return []
    ids = [m.group(1) for m in _TASK_REF_RE.finditer(s)]
    ids += [m.group(1) for m in _TASK_PATH_RE.finditer(s)]
    return ids


def _reference_targets(task: Task) -> list[str]:
    '''Ids referenced by a task via ${task:id...} in cmd / vars / when /
    latch.while — these are data edges for the boundary scan.'''
    out: list[str] = []
    for arg in (task.cmd or []):
        out += _ref_ids(arg)
    for v in (task.vars or {}).values():
        out += _ref_ids(v)
    out += _ref_ids(task.when)
    if task.latch:
        out += _ref_ids(task.latch.get('while'))
    return out


def _edges(plan: LoomPlan) -> set[tuple[str, str]]:
    '''All directed edges u -> v (v consumes u): dependencies + references.

    Self edges (a task referencing its own prior iteration) are dropped —
    they never cross a region boundary.
    '''
    by_id = {t.id for t in plan.tasks}
    edges: set[tuple[str, str]] = set()
    for t in plan.tasks:
        for d in t.depends_on:
            if d in by_id and d != t.id:
                edges.add((d, t.id))
        for r in _reference_targets(t):
            if r in by_id and r != t.id:
                edges.add((r, t.id))
    return edges


def validate_loops(plan: LoomPlan) -> None:
    '''Admit only reducible, hammock-shaped, properly-nested loops.'''
    by_id = {t.id: t for t in plan.tasks}
    latches = loops.latch_tasks(plan)
    if not latches:
        return

    # Per-latch block well-formedness + exit condition.
    headers_seen: dict[str, str] = {}
    for t in latches:
        latch = t.latch
        if not isinstance(latch, dict):
            raise LoomPlanError(f'task {t.id!r}: latch must be a mapping')
        header = latch.get('header')
        if not header:
            raise LoomPlanError(f'task {t.id!r}: latch.header is required')
        if header not in by_id:
            raise DAGError(
                f'task {t.id!r}: latch.header {header!r} is not a task')
        fuel = latch.get('fuel')
        while_expr = latch.get('while')
        if fuel is None and not while_expr:
            raise NoExitConditionError(t.id)
        if fuel is not None:
            if isinstance(fuel, bool) or not isinstance(fuel, int) or fuel <= 0:
                raise LoomPlanError(
                    f'task {t.id!r}: latch.fuel must be a positive integer, '
                    f'got {fuel!r}')
        # C3: at most one back-edge per header.
        if header in headers_seen:
            raise IrreducibleLoopError(
                f'header {header!r} has multiple back-edges '
                f'({headers_seen[header]!r} and {t.id!r}); not a natural loop')
        headers_seen[header] = t.id

    # Reducibility (C3): header must dominate latch.
    dom = loops.dominators(plan)
    for t in latches:
        header = t.latch['header']
        if header not in dom.get(t.id, set()):
            raise IrreducibleLoopError(
                f'task {t.id!r}: header {header!r} does not dominate the '
                f'latch; the loop is irreducible (not single-entry)')

    # Region bodies (C4: derived, not declared).
    regions = loops.all_regions(plan)

    # Hammock boundary scan (C1/C2).
    edges = _edges(plan)
    for latch_id, body in regions.items():
        header = by_id[latch_id].latch['header']
        for u, v in edges:
            u_in, v_in = u in body, v in body
            if (not u_in) and v_in and v != header:
                raise LoopEscapeError(
                    f'loop {latch_id!r}: edge {u!r} -> {v!r} enters the region '
                    f'at {v!r}, not the header {header!r} (single-entry '
                    f'violation)')
            if u_in and (not v_in) and u != latch_id:
                raise LoopEscapeError(
                    f'loop {latch_id!r}: edge {u!r} -> {v!r} leaves the region '
                    f'from {u!r}, not the latch {latch_id!r} (single-exit '
                    f'violation)')

    # Nesting (C5): nested / overlapping loops are not yet supported, so
    # require region bodies to be pairwise disjoint. Any shared node — a
    # properly nested inner loop or a partial overlap — is rejected.
    region_list = list(regions.items())
    for i in range(len(region_list)):
        a_id, a = region_list[i]
        for j in range(i + 1, len(region_list)):
            b_id, b = region_list[j]
            shared = a & b
            if shared:
                raise LoopNestingError(
                    f'loop regions {a_id!r} and {b_id!r} share '
                    f'{sorted(shared)!r}; nested and overlapping loops are '
                    f'not yet supported')

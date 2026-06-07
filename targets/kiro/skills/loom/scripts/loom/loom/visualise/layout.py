'''Render ordering for the rail visualisation.

renderdag draws rows top-to-bottom; a node's parents (dependencies) must
appear *below* it. We therefore emit tasks in **dependents-first** order
(reverse topological).

To keep dependency chains contiguous — so a task sits directly above the
dependency it consumes rather than interleaved with a sibling branch — we
use a depth-first (LIFO) topological sort rather than breadth-first. BFS
groups by depth and interleaves parallel branches; DFS walks one branch to
the bottom before starting the next.
'''
from __future__ import annotations

from collections import defaultdict, deque

from loom.engine.models import LoomPlan


def render_order(plan: LoomPlan) -> list[str]:
    '''Return task ids in dependents-first (reverse-topological) order.

    Dependency edges are the union of ``depends_on_all`` and
    ``depends_on_any`` (via ``Task.all_deps``). Edges to ids not present
    in the plan are ignored. Any tasks not reachable by the topological
    walk (e.g. a malformed cycle) are appended in plan order so the
    renderer never silently drops a node.
    '''
    ids = [t.id for t in plan.tasks]
    id_set = set(ids)
    deps = {t.id: [d for d in t.all_deps() if d in id_set]
            for t in plan.tasks}

    indeg = {n: 0 for n in ids}
    children: dict[str, list[str]] = defaultdict(list)
    for n in ids:
        for d in deps[n]:
            children[d].append(n)
            indeg[n] += 1

    # LIFO Kahn: seed with roots in plan order; pop from the right so the
    # walk dives depth-first down one branch before the next.
    stack = deque(n for n in ids if indeg[n] == 0)
    topo: list[str] = []
    while stack:
        n = stack.pop()
        topo.append(n)
        for c in children[n]:
            indeg[c] -= 1
            if indeg[c] == 0:
                stack.append(c)

    if len(topo) < len(ids):
        seen = set(topo)
        topo.extend(n for n in ids if n not in seen)

    return list(reversed(topo))

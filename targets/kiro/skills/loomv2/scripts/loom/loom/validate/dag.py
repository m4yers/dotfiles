"""DAG integrity checks: cycles, missing deps, duplicate ids, empty dep lists."""
from __future__ import annotations

from collections import defaultdict

from loom.engine.models import LoomPlan, Task
from loom.errors import DAGError


def validate_dag(plan: LoomPlan) -> None:
    """Run DAG integrity checks. Raises DAGError on any failure."""
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    ids = [t.id for t in tasks]
    if len(set(ids)) != len(ids):
        seen: set[str] = set()
        dupes = [i for i in ids if (i in seen) or seen.add(i)]  # type: ignore[func-returns-value]
        raise DAGError(f"duplicate task ids: {dupes!r}")
    id_set = set(ids)
    edges: dict[str, set[str]] = defaultdict(set)
    for t in tasks:
        for d in list(t.depends_on_all) + list(t.depends_on_any):
            if d not in id_set:
                raise DAGError(f"task {t.id!r} references missing dep {d!r}")
            edges[t.id].add(d)
    _detect_cycle(edges)


def _detect_cycle(edges: dict[str, set[str]]) -> None:
    color: dict[str, int] = {}  # 0=white 1=grey 2=black
    for start in edges:
        if color.get(start, 0) != 0:
            continue
        stack = [(start, iter(edges[start]))]
        color[start] = 1
        while stack:
            node, it = stack[-1]
            try:
                nxt = next(it)
            except StopIteration:
                color[node] = 2
                stack.pop()
                continue
            c = color.get(nxt, 0)
            if c == 1:
                raise DAGError(f"cycle involving {nxt!r}")
            if c == 0:
                color[nxt] = 1
                stack.append((nxt, iter(edges.get(nxt, set()))))

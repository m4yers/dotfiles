'''Topological layering for plan visualisation.

Assigns each task a layer index = longest path from any root.
Tasks with no deps are layer 0; otherwise 1 + max(deps).
Stable order within a layer: preserves plan-author order.
'''
from __future__ import annotations

from loom.engine.models import LoomPlan, Task


def layer_of(task: Task, plan: LoomPlan,
             memo: dict[str, int] | None = None) -> int:
    '''Return longest-path depth of task in plan.'''
    if memo is None:
        memo = {}
    if task.id in memo:
        return memo[task.id]
    if not task.depends_on:
        memo[task.id] = 0
        return 0
    by_id = {t.id: t for t in plan.tasks}
    depths = []
    for dep_id in task.depends_on:
        if dep_id not in by_id:
            # Should be caught by validation, but be permissive at viz time.
            continue
        depths.append(layer_of(by_id[dep_id], plan, memo))
    d = 1 + max(depths) if depths else 0
    memo[task.id] = d
    return d


def layer_of_all(plan: LoomPlan) -> list[list[Task]]:
    '''Return tasks grouped by depth. layers[i] contains tasks at depth i,
    in plan-author order.
    '''
    if not plan.tasks:
        return []
    memo: dict[str, int] = {}
    for t in plan.tasks:
        layer_of(t, plan, memo)
    max_depth = max(memo.values())
    layers: list[list[Task]] = [[] for _ in range(max_depth + 1)]
    for t in plan.tasks:
        layers[memo[t.id]].append(t)
    return layers

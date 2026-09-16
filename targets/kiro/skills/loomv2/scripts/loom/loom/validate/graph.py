"""Single-entry / single-exit invariants.

A LoomPlan MUST have exactly one task with no incoming edges (entry)
and exactly one task nothing depends on (exit). Loop back-edges live
only in latch declarations, never in the dep edge set, so they cannot
affect the counts. These invariants let a subgraph compose as a
single task via subgraph(): the child's entry input and exit output
form the composite IO contract.

Applied both to root plans and, inside composition validation, to each
child graph in isolation.
"""
from __future__ import annotations

from collections import defaultdict

from loom.engine.models import LoomPlan, Task
from loom.errors import MultipleEntriesError, MultipleExitsError


def validate_single_entry_exit(plan: LoomPlan) -> None:
    """Raise MultipleEntriesError / MultipleExitsError on rule violation."""
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    if not tasks:
        raise MultipleEntriesError("plan has no tasks")
    incoming: dict[str, int] = {t.id: 0 for t in tasks}
    outgoing: dict[str, int] = {t.id: 0 for t in tasks}
    for t in tasks:
        deps = list(t.depends_on_all) + list(t.depends_on_any)
        for d in deps:
            if d in incoming:
                incoming[t.id] += 1
                outgoing[d] += 1
    # Back-edges live only in latch declarations, never in the dep
    # edge set, so exit counting needs no latch special case: an exit
    # is simply a task nothing depends on.
    entries = [i for i, c in incoming.items() if c == 0]
    exits = [i for i, c in outgoing.items() if c == 0]
    if len(entries) != 1:
        raise MultipleEntriesError(f"expected 1 entry, found {len(entries)}: {entries!r}")
    if len(exits) != 1:
        raise MultipleExitsError(f"expected 1 exit, found {len(exits)}: {exits!r}")

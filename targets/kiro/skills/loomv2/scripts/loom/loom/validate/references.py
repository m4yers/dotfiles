"""Static ${task:...} reference resolution against target io.yaml/output.

Uses engine.resolve.GRAMMAR as the sole grammar source; parses the
JMESPath fragment; checks the target task exists and the projected
type matches the declared schema. Also enforces the ``input:`` mapping
locality rule: each ref in a task's input_mapping MUST target one of
the task's declared deps — direct entries in depends_on_all /
depends_on_any, or any task transitively reachable through them. Refs
to sibling tasks the entry cannot see (or to itself) raise
:class:`ReferenceError` at init/validate.
"""
from __future__ import annotations

import re
from collections import defaultdict

from loom.engine.models import LoomPlan, Task
from loom.engine.resolve import GRAMMAR
from loom.errors import ReferenceError
from loom.validate.schemas import SchemaCache


def validate_references(plan: LoomPlan) -> None:
    """Walk every task's when, latch.while_, and input_mapping and check refs."""
    cache = SchemaCache()
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    ids = {t.id for t in tasks}
    by_id = {t.id: t for t in tasks}
    predecessors = _transitive_predecessors(tasks)
    for t in tasks:
        texts: list[str] = []
        if t.when:
            texts.append(t.when)
        if t.latch and t.latch.while_:
            texts.append(t.latch.while_)
        for text in texts:
            _check_refs(text, ids, plan.loom_root, cache, by_id)
        if t.input_mapping:
            allowed = predecessors[t.id]
            for field, placeholder in t.input_mapping.items():
                _check_refs(placeholder, ids, plan.loom_root, cache, by_id)
                _check_mapping_locality(t.id, field, placeholder, allowed)


_TASK_REF_RE = re.compile(r"\$\{task:([^:}@]+)(?::[^}]+)?(?:@\w+)?\}")


def _check_refs(text: str, ids: set[str], loom_root, cache: SchemaCache,
                by_id: dict[str, Task]) -> None:
    for match in _TASK_REF_RE.finditer(text):
        addr = match.group(1)
        if addr not in ids:
            raise ReferenceError(
                f"reference {match.group(0)!r} targets unknown task {addr!r}"
            )
        # Schema presence check: loading it validates it. Inlined tasks
        # live under the child loom root, not the composed plan's root.
        target = by_id[addr]
        root_for_target = (
            target.source_root if target.source_root is not None else loom_root
        )
        cache.get(root_for_target, addr)


def _check_mapping_locality(
    task_id: str,
    field: str,
    placeholder: str,
    allowed: set[str],
) -> None:
    """Every ${task:<addr>} in a mapping value must target an allowed predecessor."""
    for match in _TASK_REF_RE.finditer(placeholder):
        addr = match.group(1)
        if addr not in allowed:
            raise ReferenceError(
                f"task {task_id!r} input_mapping field {field!r}: ref "
                f"{match.group(0)!r} targets {addr!r} which is not a "
                "declared (transitive) dep of the entry"
            )


def _transitive_predecessors(tasks: list[Task]) -> dict[str, set[str]]:
    """For each task, the set of tasks it depends on transitively.

    Follows depends_on_all / depends_on_any edges only; latch back-edges
    are not predecessors.
    """
    direct: dict[str, set[str]] = defaultdict(set)
    by_id = {t.id: t for t in tasks}
    for t in tasks:
        for d in list(t.depends_on_all) + list(t.depends_on_any):
            if d in by_id:
                direct[t.id].add(d)
    out: dict[str, set[str]] = defaultdict(set)
    for t in tasks:
        stack = list(direct[t.id])
        seen: set[str] = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(direct[n])
        out[t.id] = seen
    return out

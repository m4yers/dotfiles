"""Static ${task:...} reference resolution against target io.yaml/output.

Uses engine.resolve.GRAMMAR as the sole grammar source; parses each
placeholder into (address, jmespath, selector) via :func:`iter_task_refs`
so both the presence check (this module) and the downstream
subtype-projection pass (:mod:`loom.validate.subtype`) share one parse.
The captured JMESPath fragment is surfaced through the iterator; it is
no longer discarded as it was before subtype-projection landed.

Enforces the ``input:`` mapping locality rule: each ref in a task's
input_mapping MUST target one of the task's declared deps — direct
entries in depends_on_all / depends_on_any, or any task transitively
reachable through them. Refs to sibling tasks the entry cannot see (or
to itself) raise :class:`ReferenceError` at init/validate.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterator

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


# Canonical placeholder regex. Captures three groups:
#   1. address — canonical task id (may include ``/`` from subgraph
#      inlining)
#   2. selector — the ``@<sel>`` value (``prev`` or a numeric round
#      index); None when absent
#   3. jmespath — the ``:<path>`` fragment after the address+selector;
#      None when absent
# Placeholder grammar mirrors engine.mapping._FULL_TASK_REF_RE:
# ``${task:<addr>[@<sel>][:<jmespath>]}``. See references/grammar.md.
_TASK_REF_RE = re.compile(
    r"\$\{task:([^:}@]+)"
    r"(?:@([A-Za-z0-9_]+))?"
    r"(?::([^}]+))?"
    r"\}"
)


def iter_task_refs(text: str) -> Iterator[tuple[str, str | None, str | None]]:
    """Yield ``(address, jmespath, selector)`` for every task ref in ``text``.

    - ``address``: canonical task address (may contain ``/`` from
      subgraph inlining).
    - ``jmespath``: the fragment after ``:`` in the placeholder, or
      ``None`` when the placeholder omits ``:``.
    - ``selector``: the ``@<sel>`` value (``prev`` or a numeric round
      index), or ``None`` when absent.

    Consumed by :func:`_check_refs` here for the presence check and by
    :mod:`loom.validate.subtype` for the subtype-projection walk, so
    both static passes share one placeholder-grammar parser.
    """
    for match in _TASK_REF_RE.finditer(text):
        yield match.group(1), match.group(3), match.group(2)


def _check_refs(text: str, ids: set[str], loom_root, cache: SchemaCache,
                by_id: dict[str, Task]) -> None:
    from loom.engine.runner import task_source_folder

    for match in _TASK_REF_RE.finditer(text):
        addr = match.group(1)
        if addr not in ids:
            raise ReferenceError(
                f"reference {match.group(0)!r} targets unknown task {addr!r}"
            )
        # Schema presence check: loading it validates it. Folder
        # resolution goes through ``task_source_folder`` so
        # subgraph-inlined tasks (source_root) and ref-instanced
        # tasks (folder) both read their SHARED io.yaml.
        target = by_id[addr]
        cache.get(task_source_folder(loom_root, target))


def _check_mapping_locality(
    task_id: str,
    field: str,
    placeholder: str,
    allowed: set[str],
) -> None:
    """Every ${task:<addr>} in a mapping value must target an allowed predecessor.

    Refs that carry a selector (``@prev`` or ``@<int>``) reach across a
    loop back-edge — the header of a loop reads a prior round of a
    latch that itself depends forward on the header. Those refs are
    NOT modelled by transitive forward deps and skip the locality
    check here; loop admission (``validate_loops``) owns the
    structural check on the loop region.
    """
    for match in _TASK_REF_RE.finditer(placeholder):
        addr = match.group(1)
        selector = match.group(2)
        if selector is not None:
            continue
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

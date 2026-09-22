"""Subgraph flattening. Composition mechanics live here — not in a
reference file.

Why Option A (flattening): once a subgraph is inlined the rest of the
engine sees a single flat plan. Every downstream validator, scheduler,
and reference resolver operates on the composed plan without knowing
composition happened. The tradeoff — losing the runtime distinction
between parent and child — is deliberately paid because it keeps the
engine simple.

Addressing model:
  canonical address = <namespace-path>/<task-name>
where <namespace-path> is the chain of PARENT-CHOSEN SUBGRAPH INSTANCE
IDS (not graph names, not generated uuids), one segment per nesting
level. The root namespace is "".

Rewrites at inline time:
  - Parent-side ${task:<subgraph-id>...} → child exit output.yaml.
  - Child-local ${task:...} refs get the child namespace prefix.
  - ${workdir} / ${global} inside a child task remain root-scoped.

Invariants:
  - Sibling instance-ids are unique (NamespaceCollisionError).
  - Composition is invisible to downstream validators; they operate on
    the flat plan.
  - The composed plan is round-trip-equivalent with a standalone child
    run: at the boundary of a subgraph, running the child alone
    produces the same exit output as running the parent to that boundary.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from loom.engine.models import LoomPlan, SubgraphSpec, Task
from loom.errors import NamespaceCollisionError


def expand_subgraphs(plan: LoomPlan) -> LoomPlan:
    """Return a new LoomPlan with all SubgraphSpec entries inlined.

    Each child task's id is prefixed with the parent-chosen instance id.
    Parent depends_on_* on the subgraph transfer to the child entry;
    downstream parent tasks that referenced the subgraph id get their
    dependency retargeted at the child exit.
    """
    # Two-pass approach so we can rewrite parent-side dependencies AFTER
    # the child tasks are known.
    from loom.discovery import load_graph_yaml
    from loom.plan import from_graph_yaml as _load_child_plan

    new_tasks: list[Task | SubgraphSpec] = []
    seen_ids: set[str] = set()
    remap: dict[str, tuple[str, str]] = {}
    # remap[subgraph_id] = (child_entry_address, child_exit_address)

    for entry in plan.tasks:
        if isinstance(entry, SubgraphSpec):
            if entry.id in seen_ids:
                raise NamespaceCollisionError(
                    f"sibling instance id {entry.id!r} used twice at the same level"
                )
            seen_ids.add(entry.id)
            child_plan = _load_child_plan(entry.root_path, entry.graph_path)
            child_plan = expand_subgraphs(child_plan)  # recursive inline
            child_entry, child_exit = _find_entry_exit(child_plan)
            # 8 hex chars = 32 bits of entropy. Instance UIDs disambiguate
            # per-parent inlinings; collision odds are negligible at the
            # small counts of subgraph instances a single plan carries.
            inst_uid = uuid.uuid4().hex[:8]
            for child_task in child_plan.tasks:
                if not isinstance(child_task, Task):
                    continue
                prefixed = _prefix_task(child_task, entry.id, inst_uid, entry.root_path)
                # Transfer parent's depends_on_* to the child entry.
                if child_task.id == child_entry:
                    prefixed.depends_on_all = list(entry.depends_on_all) + list(prefixed.depends_on_all)
                    prefixed.depends_on_any = list(entry.depends_on_any) + list(prefixed.depends_on_any)
                    if entry.when:
                        prefixed.when = entry.when if not prefixed.when else \
                            f"({entry.when}) and ({prefixed.when})"
                    if entry.input_mapping is not None:
                        prefixed.input_mapping = dict(entry.input_mapping)
                if prefixed.id in seen_ids:
                    raise NamespaceCollisionError(
                        f"inlined child task {prefixed.id!r} collides with a sibling"
                    )
                seen_ids.add(prefixed.id)
                new_tasks.append(prefixed)
            remap[entry.id] = (f"{entry.id}/{child_entry}", f"{entry.id}/{child_exit}")
        else:
            if entry.id in seen_ids:
                raise NamespaceCollisionError(
                    f"duplicate sibling id {entry.id!r}"
                )
            seen_ids.add(entry.id)
            new_tasks.append(entry)

    # Retarget parent-side dependencies that referenced a subgraph id.
    for t in new_tasks:
        if not isinstance(t, Task):
            continue
        t.depends_on_all = [_retarget_dep(d, remap) for d in t.depends_on_all]
        t.depends_on_any = [_retarget_dep(d, remap) for d in t.depends_on_any]
        if t.when:
            for sub_id, (_entry_addr, exit_addr) in remap.items():
                t.when = _retarget_refs(t.when, sub_id, exit_addr)
        if t.input_mapping:
            for field, placeholder in list(t.input_mapping.items()):
                for sub_id, (_entry_addr, exit_addr) in remap.items():
                    placeholder = _retarget_refs(placeholder, sub_id, exit_addr)
                t.input_mapping[field] = placeholder

    return LoomPlan(loom_root=plan.loom_root, tasks=new_tasks)


def _retarget_refs(text: str, sub_id: str, exit_addr: str) -> str:
    """Rewrite ``${task:<sub_id>...}`` refs to the child exit address.

    Boundary-aware: the sub_id must be the WHOLE address (followed by
    ``:``, ``@`` or ``}``), so already-namespaced child refs like
    ``${task:<sub_id>/<child-task>:...}`` are left untouched — a blind
    prefix replace would corrupt them into
    ``<sub_id>/<exit>/<child-task>``.
    """
    for boundary in (":", "@", "}"):
        text = text.replace(
            "${task:" + sub_id + boundary,
            "${task:" + exit_addr + boundary,
        )
    return text


def _prefix_task(task: Task, instance_id: str, instance_uid: str, source_root: Path) -> Task:
    """Return a copy of ``task`` with its address prefixed by ``instance_id``.

    Also rewrites the task's own depends_on_* and when refs so that
    intra-child references resolve inside the prefixed namespace.
    """
    prefixed_id = f"{instance_id}/{task.id}"
    prefixed_mapping = (
        {k: _prefix_refs(v, instance_id) for k, v in task.input_mapping.items()}
        if task.input_mapping is not None
        else None
    )
    new = Task(
        id=prefixed_id,
        kind=task.kind,
        depends_on_all=[f"{instance_id}/{d}" for d in task.depends_on_all],
        depends_on_any=[f"{instance_id}/{d}" for d in task.depends_on_any],
        when=_prefix_refs(task.when, instance_id) if task.when else None,
        skip_output=task.skip_output,
        latch=task.latch,
        input_mapping=prefixed_mapping,
        folder=task.folder,
        status=task.status,
        iter=task.iter,
        namespace=(task.namespace + "/" + instance_id).lstrip("/"),
        inlined_from_subgraph=True,
        instance_uid=instance_uid,
        source_root=source_root,
        pinned_version=task.pinned_version,
    )
    return new


def _prefix_refs(text: str, instance_id: str) -> str:
    """Prefix child-local ${task:<id>...} refs with instance_id/."""
    from loom.engine.resolve import rename_refs

    return rename_refs(text, lambda addr: f"{instance_id}/{addr}")


def _find_entry_exit(plan: LoomPlan) -> tuple[str, str]:
    """Locate the single entry (no deps) and single exit (nothing depends on it).

    Back-edges live only in latch declarations, never in the dep edge
    set, so a latch that ends the child graph is a legitimate exit.
    """
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    ids = {t.id for t in tasks}
    incoming: dict[str, int] = {t.id: 0 for t in tasks}
    outgoing: dict[str, int] = {t.id: 0 for t in tasks}
    for t in tasks:
        deps = list(t.depends_on_all) + list(t.depends_on_any)
        for d in deps:
            if d in ids:
                incoming[t.id] += 1
                outgoing[d] += 1
    entries = [i for i, c in incoming.items() if c == 0]
    exits = [i for i, c in outgoing.items() if c == 0]
    if len(entries) != 1 or len(exits) != 1:
        # Composition validation surfaces this with the proper error class.
        raise RuntimeError(
            f"child plan lacks single entry/exit: entries={entries}, exits={exits}"
        )
    return entries[0], exits[0]


def _retarget_dep(dep: str, remap: dict[str, tuple[str, str]]) -> str:
    """If ``dep`` names a subgraph id, retarget it at that subgraph's exit."""
    if dep in remap:
        _entry, exit_addr = remap[dep]
        return exit_addr
    return dep

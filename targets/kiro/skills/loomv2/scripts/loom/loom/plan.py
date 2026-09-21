"""Plan and task factories, plus graph.yaml <-> LoomPlan conversion.

Public API. Every function and class here carries a docstring stating
the contract, args, return shape, raises list, and a minimal example.
This module is the API doc for plan construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from loom.engine.models import (
    ActionSpec,
    LoomPlan,
    LoopBlock,
    SubgraphSpec,
    Task,
)


def _make_task(
    kind: str,
    id: str,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    latch: "LoopBlock | None" = None,
    input_mapping: dict[str, str] | None = None,
) -> Task:
    """Shared task-factory body. Enforces non-empty dep lists."""
    if depends_on_all is not None and not depends_on_all:
        raise ValueError(f"task {id!r}: depends_on_all must be non-empty when supplied")
    if depends_on_any is not None and not depends_on_any:
        raise ValueError(f"task {id!r}: depends_on_any must be non-empty when supplied")
    return Task(
        id=id,
        kind=kind,
        depends_on_all=list(depends_on_all or []),
        depends_on_any=list(depends_on_any or []),
        when=when,
        latch=latch,
        input_mapping=dict(input_mapping) if input_mapping is not None else None,
    )


def tool(
    id: str,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    latch: "LoopBlock | None" = None,
    input_mapping: dict[str, str] | None = None,
) -> Task:
    """Create a tool task.

    Body: ``<loom_root>/<id>/tool.py`` exposes
    ``def <snake_case(id)>(inp: <TaskName>Input) -> <TaskName>Output``,
    where ``<TaskName>Input`` and ``<TaskName>Output`` are dataclasses
    generated in ``<loom_root>/<id>/io_types.py`` by
    ``$LOOM task io-python <id>``. Each generated class carries
    ``VERSION: ClassVar[int]`` matching ``io.yaml/version``; dispatch
    raises ``ToolIOVersionMismatchError`` on drift.

    Raises ValueError on empty dep lists. Returns a Task with kind='tool'.
    """
    return _make_task("tool", id, depends_on_all, depends_on_any, when, latch, input_mapping)


def agent(
    id: str,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    latch: "LoopBlock | None" = None,
    input_mapping: dict[str, str] | None = None,
) -> Task:
    """Create an agent task.

    Body: <loom_root>/<id>/prompt.md.j2 rendered by the engine; the
    sub-agent writes output.yaml via the output CLI.
    """
    return _make_task("agent", id, depends_on_all, depends_on_any, when, latch, input_mapping)


def human(
    id: str,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    latch: "LoopBlock | None" = None,
    input_mapping: dict[str, str] | None = None,
) -> Task:
    """Create a human-gate task.

    Body: <loom_root>/<id>/message.md.j2 rendered for the current agent
    to present to the user.
    """
    return _make_task("human", id, depends_on_all, depends_on_any, when, latch, input_mapping)


def subgraph(
    id: str,
    root: Path,
    depends_on_all: list[str] | None = None,
    depends_on_any: list[str] | None = None,
    when: str | None = None,
    input_mapping: dict[str, str] | None = None,
) -> SubgraphSpec:
    """Declare a subgraph instance.

    ``id`` is the parent-chosen subgraph instance id (kebab-case, unique
    among siblings). ``root`` points at the child skill's loom root. At
    loom.init / loom.extend the engine loads the child graph.yaml,
    validates it, and INLINES the child tasks into the parent plan with
    canonical addresses prefixed by ``id``.

    Raises NamespaceCollisionError if ``id`` collides with a sibling.
    """
    if depends_on_all is not None and not depends_on_all:
        raise ValueError(f"subgraph {id!r}: depends_on_all must be non-empty when supplied")
    if depends_on_any is not None and not depends_on_any:
        raise ValueError(f"subgraph {id!r}: depends_on_any must be non-empty when supplied")
    return SubgraphSpec(
        id=id,
        root_path=Path(root),
        depends_on_all=list(depends_on_all or []),
        depends_on_any=list(depends_on_any or []),
        when=when,
        input_mapping=dict(input_mapping) if input_mapping is not None else None,
    )


def latch(
    header: str,
    fuel: int | None = None,
    while_: str | None = None,
) -> LoopBlock:
    """Build a latch block.

    Args:
        header: task id the back-edge points at.
        fuel: positive countdown, decremented per round.
        while_: predicate; loop continues while true.

    At least one of fuel / while_ MUST be given (enforced at loom.init
    via NoExitConditionError).
    """
    if fuel is None and while_ is None:
        raise ValueError("latch: supply at least one of fuel / while_")
    if fuel is not None and fuel < 1:
        raise ValueError("latch: fuel must be a positive integer")
    return LoopBlock(header=header, fuel=fuel, while_=while_)


def make_plan(*tasks: Task | SubgraphSpec, loom_root: Path) -> LoomPlan:
    """Assemble a LoomPlan from tasks and subgraph specs.

    ``loom_root`` is the path loom uses to resolve task ids to folders.
    Tasks may be interleaved with SubgraphSpec instances; the engine
    inlines subgraphs at loom.init / loom.extend.

    Raises DAGError on duplicate ids.
    """
    if not tasks:
        raise ValueError("make_plan: at least one task required")
    return LoomPlan(loom_root=Path(loom_root), tasks=list(tasks))


class _LoomPlanClassmethods:
    """Namespace holder for LoomPlan.from_graph_yaml / to_graph_yaml.

    These live as classmethods on LoomPlan; see engine/models.py for the
    bindings. The bodies below are re-exported for import convenience.
    """


def from_graph_yaml(loom_root: Path, graph: Path | str | None = None) -> LoomPlan:
    """Load a graph file (default ``<loom_root>/graph.yaml``) into a LoomPlan.

    Validates the file against schemas/graph.yaml and stamps each task's
    ``pinned_version`` from the graph entry. Raises GraphYamlError on
    schema failure.

    Entries carrying a ``ref: <folder-name>`` field populate the
    resulting Task's ``folder`` with the resolved shared folder under
    ``loom_root``, so the id and the backing folder decouple. ``ref``
    on ``kind: subgraph`` entries is rejected via
    :class:`TaskRefError` (defense-in-depth alongside the schema
    check).
    """
    from loom.discovery import load_graph_yaml, resolve_ref_folder
    from loom.errors import TaskRefError

    entries = load_graph_yaml(Path(loom_root), graph)
    tasks: list[Task | SubgraphSpec] = []
    for entry in entries["tasks"]:
        kind = entry["kind"]
        ref = entry.get("ref")
        common = {
            "id": entry["id"],
            "depends_on_all": entry.get("depends_on_all"),
            "depends_on_any": entry.get("depends_on_any"),
            "when": entry.get("when"),
            "input_mapping": entry.get("input"),
        }
        if kind == "subgraph":
            if ref is not None:
                raise TaskRefError(
                    f"subgraph entry {entry['id']!r} declares `ref: "
                    f"{ref!r}`; `ref` is not valid on kind=subgraph "
                    "(use the entry's own `root:` for cross-graph reuse)."
                )
            raw_root = Path(entry["root"])
            child_root = raw_root if raw_root.is_absolute() else (Path(loom_root) / raw_root).resolve()
            task = subgraph(root=child_root, **common)
        else:
            factory = {"tool": tool, "agent": agent, "human": human}[kind]
            task = factory(**common)
            task.pinned_version = entry["version"]
            if ref is not None:
                task.folder = resolve_ref_folder(Path(loom_root), ref)
        tasks.append(task)
    # Attach latch blocks to their tasks.
    for latch_entry in entries.get("latches", []):
        target = next(t for t in tasks if isinstance(t, Task) and t.id == latch_entry["task"])
        target.latch = latch(
            header=latch_entry["header"],
            fuel=latch_entry.get("fuel"),
            while_=latch_entry.get("while_"),
        )
    return LoomPlan(loom_root=Path(loom_root), tasks=tasks)


def to_graph_yaml(plan: LoomPlan, path: Path) -> None:
    """Emit ``plan`` as a graph.yaml at ``path``.

    Stamps each entry with the CURRENT io.yaml version by resolving
    each task's io.yaml/body source folder via
    :func:`loom.engine.runner.task_source_folder`, so ref-instanced
    tasks (whose backing folder differs from the id) restamp against
    the shared folder. Tasks loaded with a ``ref:`` emit that field
    back on the entry (``ref = t.folder.name``). Atomic write.
    """
    import yaml

    from loom.discovery import load_io_yaml
    from loom.engine.runner import task_source_folder
    from loom.engine.store import atomic_write

    task_entries: list[dict] = []
    latch_entries: list[dict] = []
    for t in plan.tasks:
        if isinstance(t, SubgraphSpec):
            entry = {
                "id": t.id,
                "kind": "subgraph",
                "version": 1,
                "root": str(t.root_path),
            }
        else:
            io = load_io_yaml(task_source_folder(plan.loom_root, t))
            entry = {"id": t.id, "kind": t.kind, "version": io.version}
            if t.folder is not None:
                # Emit `ref` when the backing folder differs from the
                # id; the field's whole reason to exist is decoupling
                # instance-id from shared folder.
                entry["ref"] = t.folder.name
            if t.latch:
                latch_entries.append({
                    "task": t.id,
                    "header": t.latch.header,
                    **({"fuel": t.latch.fuel} if t.latch.fuel is not None else {}),
                    **({"while_": t.latch.while_} if t.latch.while_ is not None else {}),
                })
        if t.depends_on_all:
            entry["depends_on_all"] = list(t.depends_on_all)
        if t.depends_on_any:
            entry["depends_on_any"] = list(t.depends_on_any)
        if t.when:
            entry["when"] = t.when
        if t.input_mapping is not None:
            entry["input"] = dict(t.input_mapping)
        task_entries.append(entry)

    doc = {"tasks": task_entries}
    if latch_entries:
        doc["latches"] = latch_entries

    atomic_write(Path(path), yaml.safe_dump(doc, sort_keys=False))


# Bind classmethods.
LoomPlan.from_graph_yaml = staticmethod(from_graph_yaml)  # type: ignore[attr-defined]
LoomPlan.to_graph_yaml = to_graph_yaml  # type: ignore[assignment]

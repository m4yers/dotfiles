"""Core dataclasses for plans, tasks, subgraphs, and runtime actions.

Task carries the canonical address in ``id`` (instance-id chain + task
name). Inlined tasks record ``instance_uid`` and ``source_root`` as
metadata alongside the address; those fields are telemetry only and
never appear in author-facing identity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


Kind = Literal["tool", "agent", "human"]
Status = Literal["pending", "ready", "running", "done", "failed", "skipped"]


@dataclass
class LoopBlock:
    """Latch parameters. Attached to a Task to make it a loop latch."""

    header: str
    fuel: int | None = None
    while_: str | None = None


@dataclass
class Task:
    """A single tool/agent/human task.

    ``folder`` decouples the task's on-disk io.yaml + body location
    from its ``id``. Two writers populate it:

    - Subgraph inlining (:mod:`loom.engine.inline`) preserves the
      child task's original ``folder`` alongside ``source_root`` so
      the child's schemas and bodies keep loading from the child
      loom tree.
    - graph.yaml ``ref: <folder-name>`` (parsed in
      :func:`loom.plan.from_graph_yaml`) points a graph entry at a
      shared kebab-cased folder under the SAME loom root, so
      multiple entries can share one task-folder definition while
      keeping distinct ``id``s for addressing, workdirs, and
      placeholders.

    In both cases every downstream consumer that resolves the
    io.yaml / body location through
    :func:`loom.engine.runner.task_source_folder` (runner, builders,
    versions, tool_entry, templates, validators) picks up the
    decoupled folder for free.
    """

    id: str
    kind: Kind
    depends_on_all: list[str] = field(default_factory=list)
    depends_on_any: list[str] = field(default_factory=list)
    when: str | None = None
    latch: LoopBlock | None = None
    input_mapping: dict[str, str] | None = None
    # Optional post-composition metadata:
    folder: Path | None = None
    status: Status = "pending"
    iter: int = 0
    namespace: str = ""
    inlined_from_subgraph: bool = False
    instance_uid: str | None = None
    source_root: Path | None = None
    pinned_version: int | None = None


@dataclass
class SubgraphSpec:
    """A subgraph reference. Replaced by inlined child tasks at loom.init."""

    id: str
    root_path: Path
    depends_on_all: list[str] = field(default_factory=list)
    depends_on_any: list[str] = field(default_factory=list)
    when: str | None = None
    input_mapping: dict[str, str] | None = None


@dataclass
class LoomPlan:
    """A plan is a set of tasks and (unexpanded) subgraph specs."""

    loom_root: Path
    tasks: list[Task | SubgraphSpec] = field(default_factory=list)

    # LoomPlan.from_graph_yaml / to_graph_yaml are bound in loom.plan.


@dataclass
class ActionSpec:
    """The next-step batch yielded by LoomRuntime.next()."""

    tasks: list[dict[str, Any]]

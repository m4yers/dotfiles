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
    """A single tool/agent/human task."""

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

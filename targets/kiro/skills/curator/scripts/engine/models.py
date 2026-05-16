"""Core data models — Plan and Task.

Two objects describe the curator engine's data:

- ``Task`` — one node in the plan DAG; carries metadata, dependencies,
              inputs, AND its execution status. The scheduler does
              NOT interpret ``kind``; it only tracks ``status`` and
              workdir creation. The orchestrator dispatches per-kind.
- ``Plan`` — ordered list of tasks. Plan is mutable: ``status`` is
              updated in place as tasks transition. ``extend()``
              appends new tasks (default status ``pending``).

Plan is the single source of truth — there is no separate state file.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# Lifecycle of a single task. Linear: pending → running → done|failed.
STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE    = "done"
STATUS_FAILED  = "failed"

VALID_STATUSES = (STATUS_PENDING, STATUS_RUNNING, STATUS_DONE, STATUS_FAILED)
TERMINAL_STATUSES = (STATUS_DONE, STATUS_FAILED)


@dataclass
class Task:
    """One node in the plan DAG.

    The scheduler reads ``id``, ``depends_on``, and ``status`` for
    scheduling decisions. Everything else is opaque payload that the
    orchestrator interprets per ``kind``.
    """

    id: str
    kind: str                                          # tool | agent | human

    depends_on: list[str] = field(default_factory=list)

    # tool kind
    cmd: list[str] | None = None

    # agent kind — single attempt; engine treats agent tasks as
    # opaque external work that the orchestrator dispatches.
    agent: str | None = None                           # sub-agent role name
    template: str | None = None                        # kind name → templates/<kind>/
    vars: dict[str, Any] = field(default_factory=dict)
    judge: dict[str, Any] | None = None                # nested {agent, template, vars}

    # Execution status — mutated in place by algorithm.mark_*
    status: str = STATUS_PENDING

    # free-form pass-through (per-kind hints, etc.)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        out = {}
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, (list, dict)) and len(v) == 0:
                continue
            out[k] = v
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Plan:
    """A plan is an ordered list of tasks. Mutable in place: each
    task's ``status`` field carries its execution state.

    Plan is the single source of truth on disk (``plan.yaml``). There
    is no separate ``state.yaml``."""

    tasks: list[Task] = field(default_factory=list)

    def get(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(f"task not in plan: {task_id}")

    def ids(self) -> set[str]:
        return {t.id for t in self.tasks}

    def to_dict(self) -> dict:
        return {"tasks": [t.to_dict() for t in self.tasks]}

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(tasks=[Task.from_dict(t) for t in d.get("tasks", [])])

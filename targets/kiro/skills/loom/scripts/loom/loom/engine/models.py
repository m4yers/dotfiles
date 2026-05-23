'''Data models for loom engine.'''
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

STATUS_PENDING = 'pending'
STATUS_READY = 'ready'
STATUS_RUNNING = 'running'
STATUS_DONE = 'done'
STATUS_FAILED = 'failed'
STATUS_SKIPPED = 'skipped'

VALID_STATUSES = (STATUS_PENDING, STATUS_READY, STATUS_RUNNING,
                  STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED)
TERMINAL_STATUSES = (STATUS_DONE, STATUS_FAILED, STATUS_SKIPPED)


@dataclass
class Task:
    '''One node in the plan DAG. Engine reads id, kind, depends_on, when, status
    for scheduling; everything else is per-kind payload.
    '''
    id: str
    kind: Literal['tool', 'agent', 'human']

    depends_on: list[str] = field(default_factory=list)
    when: str | None = None
    output_schema: str | None = None

    # tool kind
    cmd: list[str] | None = None

    # agent kind
    agent: str | None = None
    template: str | None = None
    vars: dict[str, Any] = field(default_factory=dict)

    # execution
    status: str = STATUS_PENDING

    def to_dict(self) -> dict:
        '''Return dict omitting keys whose value is None or empty list/dict.'''
        d = asdict(self)
        return {k: v for k, v in d.items()
                if v is not None and v != [] and v != {}}

    @classmethod
    def from_dict(cls, d: dict) -> 'Task':
        '''Construct from dict; unknown keys ignored.'''
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class LoomPlan:
    '''Ordered list of tasks. Mutable; status mutated in place.
    Single source of truth on disk (plan.yaml). No separate state.
    '''
    tasks: list[Task] = field(default_factory=list)

    def get(self, task_id: str) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise KeyError(f'task not in plan: {task_id}')

    def ids(self) -> set[str]:
        return {t.id for t in self.tasks}

    def to_dict(self) -> dict:
        return {'tasks': [t.to_dict() for t in self.tasks]}

    @classmethod
    def from_dict(cls, d: dict) -> 'LoomPlan':
        '''Deserialization only; validation runs at loom.init/extend time.'''
        return cls(tasks=[Task.from_dict(t) for t in (d.get('tasks') or [])])

    @classmethod
    def from_yaml(cls, path: str | Path) -> 'LoomPlan':
        '''Load a plan from a YAML file. Deserialization only.'''
        import yaml
        p = Path(path).expanduser()
        if not p.exists():
            raise FileNotFoundError(f'plan file not found: {p}')
        return cls.from_dict(yaml.safe_load(p.read_text(encoding='utf-8')) or {})


@dataclass
class ActionSpec:
    '''Returned by LoomRuntime.next() when an external batch is ready.'''
    workdir: Path
    tasks: list[dict]

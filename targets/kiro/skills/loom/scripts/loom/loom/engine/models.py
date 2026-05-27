'''Data models for loom engine.'''
from __future__ import annotations

import warnings
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
    '''One node in the plan DAG. Engine reads id, kind, depends_on_all,
    depends_on_any, when, status for scheduling; everything else is
    per-kind payload.

    Dependency semantics
    --------------------
    A task becomes ready when:
      - every id listed in ``depends_on_all`` is in a terminal status
        (done, failed, or skipped), AND
      - if ``depends_on_any`` is non-empty, at least one of its ids
        is in a terminal status.

    Cascade-skip applies when either list is non-empty and EVERY id
    in that list has status ``skipped`` — there is no upstream
    output for the task to consume.

    Legacy ``depends_on``
    --------------------
    The pre-1.0 ``depends_on`` field is deprecated; it is silently
    migrated to ``depends_on_all`` on construction and on YAML load.
    The factory functions in ``loom.plan`` warn (FutureWarning) when
    callers pass ``depends_on=`` so authors can update their code.
    The ``Task.depends_on`` attribute remains populated post-migration
    as the union of the two new lists, so consumers that just want
    "every upstream id" (renderer, layout, validators) can keep
    reading it.
    '''
    id: str
    kind: Literal['tool', 'agent', 'human']

    # New canonical dependency lists. Schedulers consult these
    # directly; everything else can use ``depends_on`` (union).
    depends_on_all: list[str] = field(default_factory=list)
    depends_on_any: list[str] = field(default_factory=list)

    # Deprecated. On construction, a non-empty value is migrated
    # into ``depends_on_all`` (a FutureWarning fires from the
    # factory callsite). After ``__post_init__``, this field
    # always equals the union of the two canonical lists so
    # legacy consumers (template context, viz layout) keep
    # working without per-callsite migration.
    depends_on: list[str] = field(default_factory=list)

    when: str | None = None
    output_schema: str | None = None

    # tool kind
    cmd: list[str] | None = None

    # agent kind
    agent: str | None = None
    template: str | None = None
    template_search_paths: list[str] | None = None
    vars: dict[str, Any] = field(default_factory=dict)

    # execution
    status: str = STATUS_PENDING

    def __post_init__(self) -> None:
        '''Reconcile the legacy ``depends_on`` field.

        Migration order:

        1. If the caller supplied a non-empty ``depends_on`` AND
           a non-empty ``depends_on_all``, raise — the caller is
           mixing the legacy and new APIs.
        2. If only the legacy field is set, copy it into
           ``depends_on_all`` (no warning here — the warning
           fires at the user-facing entry point: the factory
           functions in ``loom.plan`` and ``Task.from_dict``).
        3. After migration, ``depends_on`` is set to the
           order-preserving union of the two canonical lists so
           legacy readers keep working.
        '''
        legacy = list(self.depends_on)
        if legacy:
            if self.depends_on_all:
                from loom.errors import LoomPlanError
                raise LoomPlanError(
                    f'task {self.id!r}: depends_on (deprecated) '
                    f'cannot coexist with depends_on_all; pick one'
                )
            self.depends_on_all = legacy
        # Always recompute as the union — also covers the case
        # where the caller used only the new fields.
        self.depends_on = self._compute_union()

    def _compute_union(self) -> list[str]:
        '''Order-preserving union of all + any dependency lists.'''
        seen: set[str] = set()
        out: list[str] = []
        for dep in self.depends_on_all + self.depends_on_any:
            if dep not in seen:
                seen.add(dep)
                out.append(dep)
        return out

    def all_deps(self) -> list[str]:
        '''Order-preserving union of ``depends_on_all`` and
        ``depends_on_any``. Use for graph operations
        (validation, layout, transitive walks) that don't
        distinguish between the two.

        Equivalent to ``task.depends_on``; this method exists
        for callers that want an explicit, descriptive name.
        '''
        return self._compute_union()

    def to_dict(self) -> dict:
        '''Return dict omitting keys whose value is None or empty
        list/dict.

        The deprecated ``depends_on`` field is never serialized —
        its value is the redundant union of the two canonical
        fields, and round-tripping it would re-trigger
        deprecation warnings on read.
        '''
        d = asdict(self)
        d.pop('depends_on', None)
        return {k: v for k, v in d.items()
                if v is not None and v != [] and v != {}}

    @classmethod
    def from_dict(cls, d: dict) -> 'Task':
        '''Construct from dict; unknown keys ignored.

        If the dict carries a legacy ``depends_on`` key, it is
        silently migrated into ``depends_on_all`` (an error if
        the new field is also present). YAML files written by
        an older loom version load without spam; new YAML
        files round-trip cleanly because ``to_dict`` drops the
        legacy key on write.
        '''
        d = dict(d)
        legacy = d.pop('depends_on', None)
        if legacy:
            if d.get('depends_on_all'):
                from loom.errors import LoomPlanError
                raise LoomPlanError(
                    f'task {d.get("id")!r}: depends_on (deprecated) '
                    f'cannot coexist with depends_on_all; pick one'
                )
            d['depends_on_all'] = list(legacy)
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

"""Persistence layer for plan + state + task outputs.

Files (all YAML):

- ``<workdir>/plan.yaml``   — plan definition (grows via plan extend)
- ``<workdir>/tasks/<id>/`` — per-task subdir; canonical output at
                              ``<workdir>/tasks/<id>/output.yaml``

All writes are atomic (tmp + ``os.replace``) so a crash mid-write
never leaves a partial file that the next invocation would reject.

Concurrent invocations are NOT guaranteed safe; the calling skill is
expected to serialize its own calls to the scheduler. Ready-set
computation itself is stateless given a valid (plan, state) pair, so
as long as the caller does not race ``task next`` against ``task
complete`` on overlapping tasks, nothing is lost.
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

from engine.models import Plan


def _dump_yaml(data) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


# ── plan.yaml ──────────────────────────────────────────

def plan_path(workdir: Path) -> Path:
    return Path(workdir) / "plan.yaml"


def load_plan(workdir: Path) -> Plan:
    p = plan_path(workdir)
    if not p.exists():
        raise FileNotFoundError(f"plan.yaml not found at {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return Plan.from_dict(data)


def save_plan(workdir: Path, plan: Plan) -> None:
    _atomic_write(plan_path(workdir), _dump_yaml(plan.to_dict()))


# ── task subdir + output.yaml ──────────────────────────


def _numbered_name(index: int, task_id: str) -> str:
    """Canonical numbered subdir name: '01-fetch', '02-convert', ..."""
    return f"{index:02d}-{task_id}"


def task_dir(workdir: Path, task_id: str,
              plan: "Plan | None" = None) -> Path:
    """Per-task workdir at ``<workdir>/tasks/<NN-task_id>/``.

    If ``plan`` is provided, the index is computed from the task's
    1-based position in ``plan.tasks``.

    If ``plan`` is omitted, the function scans ``<workdir>/tasks/``
    for an existing dir whose name ends with ``-<task_id>`` (or
    matches ``<task_id>`` exactly for legacy unnumbered runs).
    Falls back to bare ``<task_id>`` if no match exists yet.
    """
    if plan is not None:
        for i, t in enumerate(plan.tasks, start=1):
            if t.id == task_id:
                return Path(workdir) / "tasks" / _numbered_name(i, task_id)
        raise KeyError(f"task not in plan: {task_id}")

    tasks = Path(workdir) / "tasks"
    if tasks.exists():
        for child in sorted(tasks.iterdir()):
            if not child.is_dir():
                continue
            if child.name == task_id:
                return child
            if child.name.endswith(f"-{task_id}"):
                return child
    return tasks / task_id


def ensure_task_dir(workdir: Path, task_id: str,
                      plan: "Plan | None" = None) -> Path:
    """Create the numbered per-task subdir if missing; return its
    absolute path. Plan is required at first creation."""
    d = task_dir(workdir, task_id, plan=plan)
    d.mkdir(parents=True, exist_ok=True)
    return d


def task_output_path(workdir: Path, task_id: str,
                       plan: "Plan | None" = None) -> Path:
    """Canonical output artifact: ``<task_dir>/output.yaml``."""
    return task_dir(workdir, task_id, plan=plan) / "output.yaml"


def load_task_output(workdir: Path, task_id: str,
                       plan: "Plan | None" = None) -> dict:
    """Read a completed task's output.yaml. Raises if missing."""
    p = task_output_path(workdir, task_id, plan=plan)
    if not p.exists():
        raise FileNotFoundError(
            f"output.yaml missing for task {task_id!r}: {p}"
        )
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data if data is not None else {}

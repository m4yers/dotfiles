"""Programmatic helpers for `output init` and `output add`.

Consumers: __main__.py CLI dispatch and tests.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import jsonschema
import yaml

from loom.discovery import load_io_yaml, resolve_task_folder
from loom.engine.models import LoomPlan, Task
from loom.engine.store import (
    read_plan_yaml,
    round_folder,
    task_folder,
    write_output_yaml,
)
from loom.errors import OutputSchemaError


def _target_folder(workdir: Path, plan: LoomPlan, task_id: str) -> Path:
    """Current-round write folder (flat for non-loop tasks)."""
    from loom.engine.loops import region_members

    folder = task_folder(Path(workdir), plan, task_id)
    return round_folder(folder, is_loop_body=task_id in region_members(plan))


def _seed_from_schema(schema: dict) -> Any:
    """Seed a value from a JSON Schema. Top-level object → {}; array → []."""
    t = schema.get("type")
    if t == "object":
        return {}
    if t == "array":
        return []
    return None


def output_init(workdir: Path, task_id: str) -> None:
    """Seed ``output.yaml`` from the task's io.yaml/output."""
    plan = read_plan_yaml(Path(workdir))
    task = _task(plan, task_id)
    folder = task.folder if task.folder else resolve_task_folder(plan.loom_root, task_id)
    io = load_io_yaml(folder)
    write_output_yaml(_target_folder(workdir, plan, task_id), _seed_from_schema(io.output_schema))


def output_add(workdir: Path, task_id: str, assignments: list[str]) -> None:
    """Apply ``path=value`` assignments to output.yaml, coerce, validate, write.

    For a loop-body task the writes land in the current ``iter-NN/``
    round dir.
    """
    plan = read_plan_yaml(Path(workdir))
    task = _task(plan, task_id)
    folder = task.folder if task.folder else resolve_task_folder(plan.loom_root, task_id)
    io = load_io_yaml(folder)
    target_folder = _target_folder(workdir, plan, task_id)
    target = target_folder / "output.yaml"
    doc: Any = yaml.safe_load(target.read_text()) if target.exists() else {}
    for a in assignments:
        path, _, raw_value = a.partition("=")
        _set_by_path(doc, path.split("."), _coerce(raw_value))
    try:
        jsonschema.validate(doc, io.output_schema)
    except jsonschema.ValidationError as exc:
        raise OutputSchemaError(task_id, exc.message) from exc
    write_output_yaml(target_folder, doc)


def _task(plan: LoomPlan, task_id: str) -> Task:
    for t in plan.tasks:
        if isinstance(t, Task) and t.id == task_id:
            return t
    raise KeyError(task_id)


def _set_by_path(doc: Any, path: list[str], value: Any) -> None:
    """Set ``value`` at dotted path. Numeric segments are array indices."""
    cur = doc
    for i, seg in enumerate(path[:-1]):
        nxt_key: Any = int(seg) if seg.isdigit() else seg
        if isinstance(nxt_key, int):
            while len(cur) <= nxt_key:
                cur.append({})
            if not isinstance(cur[nxt_key], (dict, list)):
                cur[nxt_key] = {}
            cur = cur[nxt_key]
        else:
            if nxt_key not in cur or not isinstance(cur[nxt_key], (dict, list)):
                # Look ahead: if next segment is numeric, seed a list.
                cur[nxt_key] = [] if (i + 1 < len(path) and path[i + 1].isdigit()) else {}
            cur = cur[nxt_key]
    last = path[-1]
    if last.isdigit() and isinstance(cur, list):
        idx = int(last)
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = value
    else:
        cur[last] = value


def _coerce(raw: str) -> Any:
    """Best-effort coercion of a CLI string value to a scalar."""
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw

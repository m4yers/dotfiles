'''Generic schema-driven output writer for loom tasks.

Two CLI commands cover every loom agent task:

* ``loom output init <workdir> --task <id>``
  Looks up the task's ``output_schema`` from ``<workdir>/plan.yaml``,
  embeds it as ``_schema`` in the output file, and seeds top-level
  array / object containers from the schema.

* ``loom output add <workdir> --task <id> --set path=value [--set ...]``
  Applies one or more dotted ``path=value`` assignments, then
  validates the resulting file against the embedded schema.

Loom already validates outputs at ``runtime.complete()``; this CLI
exists so sub-agents (LLM tasks dispatched by the orchestrator) can
produce schema-valid output.yaml files via shell calls instead of
free-form ``fs_write``. Eager validation in ``add`` catches schema
violations before ``complete()``.

Schema embedding makes every output self-describing — the agent's
output is identical whether produced by hand or via this CLI, and
the ``_schema`` field is stripped on read by callers that need the
raw payload.
'''
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from loom.engine import store


# ── helpers ──────────────────────────────────────────────────────


def _emit(payload: dict) -> None:
    '''Write a one-line JSON status to stdout. Mirrors curator.utils.emit.'''
    sys.stdout.write(json.dumps(payload, sort_keys=False) + '\n')
    sys.stdout.flush()


def _fail(message: str, **extra: Any) -> 'NoReturn':  # type: ignore[name-defined]
    payload = {'ok': False, 'error': message, **extra}
    sys.stderr.write(json.dumps(payload, sort_keys=False) + '\n')
    sys.stderr.flush()
    raise SystemExit(1)


def _load_plan(workdir: Path):
    if not store.plan_path(workdir).exists():
        _fail(f'no plan.yaml at {workdir}; not a loom workdir')
    return store.load_plan(workdir)


def _task_schema_path(workdir: Path, task_id: str) -> Path:
    plan = _load_plan(workdir)
    by_id = {t.id: t for t in plan.tasks}
    task = by_id.get(task_id)
    if task is None:
        _fail(f'task {task_id!r} not in plan')
    schema = getattr(task, 'output_schema', None)
    if not schema:
        _fail(f'task {task_id!r} has no output_schema')
    return Path(schema)


def _task_output_path(workdir: Path, task_id: str) -> Path:
    plan = _load_plan(workdir)
    by_id = {t.id: t for t in plan.tasks}
    if task_id not in by_id:
        _fail(f'task {task_id!r} not in plan')
    return store.task_output_write_path(workdir, plan, task_id)


def _ensure_task_dir(workdir: Path, task_id: str) -> None:
    plan = _load_plan(workdir)
    if task_id not in {t.id for t in plan.tasks}:
        return
    store.ensure_task_dir(workdir, plan, task_id)


def _load_schema_at(p: Path) -> dict:
    if not p.exists():
        _fail(f'schema not found at {p}')
    return yaml.safe_load(p.read_text(encoding='utf-8'))


def _initial_data(schema: dict) -> dict:
    '''Build the initial output shape from the schema's top-level
    properties. Arrays start as ``[]``, objects as ``{}``, scalars
    are left absent (the agent fills them via ``add``).'''
    data: dict = {}
    for name, sub in (schema.get('properties') or {}).items():
        t = sub.get('type')
        if t == 'array':
            data[name] = []
        elif t == 'object':
            data[name] = {}
    return data


def _atomic_save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                       default_flow_style=False),
        encoding='utf-8',
    )
    os.replace(tmp, path)


def _load_output(path: Path) -> dict:
    if not path.exists():
        _fail(f'output file does not exist: {path}; '
              f'call ``loom output init`` first')
    return yaml.safe_load(path.read_text(encoding='utf-8')) or {}


# ── path resolution ─────────────────────────────────────────────


_PATH_PART = re.compile(r'^(?:\d+|[^.\[]+)$')


def _split_path(path: str) -> list[str]:
    if not path:
        _fail('empty path')
    parts = path.split('.')
    for p in parts:
        if not _PATH_PART.match(p):
            _fail(f'invalid path segment {p!r} in {path!r}')
    return parts


def _set_path(root: Any, path: str, value: Any) -> Any:
    parts = _split_path(path)
    cursor = root
    for i, part in enumerate(parts[:-1]):
        next_part = parts[i + 1]
        next_is_index = next_part.isdigit()

        if part.isdigit():
            idx = int(part)
            if not isinstance(cursor, list):
                _fail(f'path {path!r}: expected list at segment '
                      f'{".".join(parts[:i])}, got {type(cursor).__name__}')
            while len(cursor) <= idx:
                cursor.append([] if next_is_index else {})
            cursor = cursor[idx]
        else:
            if not isinstance(cursor, dict):
                _fail(f'path {path!r}: expected object at segment '
                      f'{".".join(parts[:i])}, got {type(cursor).__name__}')
            if part not in cursor or cursor[part] is None:
                cursor[part] = [] if next_is_index else {}
            cursor = cursor[part]

    last = parts[-1]
    if last.isdigit():
        idx = int(last)
        if not isinstance(cursor, list):
            _fail(f'path {path!r}: expected list at parent, got '
                  f'{type(cursor).__name__}')
        while len(cursor) <= idx:
            cursor.append(None)
        cursor[idx] = value
    else:
        if not isinstance(cursor, dict):
            _fail(f'path {path!r}: expected object at parent, got '
                  f'{type(cursor).__name__}')
        cursor[last] = value
    return root


# ── type coercion ───────────────────────────────────────────────


def _resolve_type_for_path(schema: dict, path: list[str]) -> dict | None:
    cur = schema
    for part in path:
        if cur.get('type') == 'array':
            cur = cur.get('items') or {}
            if part.isdigit():
                continue
            cur = (cur.get('properties') or {}).get(part)
            if cur is None:
                return None
        elif cur.get('type') == 'object' or 'properties' in cur:
            cur = (cur.get('properties') or {}).get(part)
            if cur is None:
                return None
        else:
            return None
    return cur


def _coerce(value: str, leaf_schema: dict | None) -> Any:
    if value == 'null':
        return None
    if leaf_schema is None:
        return value
    t = leaf_schema.get('type')
    types = t if isinstance(t, list) else [t]
    if 'null' in types and value in ('', 'null', 'None'):
        return None
    if 'integer' in types:
        try:
            return int(value)
        except ValueError:
            _fail(f'value {value!r} is not a valid integer')
    if 'number' in types:
        try:
            return float(value)
        except ValueError:
            _fail(f'value {value!r} is not a valid number')
    if 'boolean' in types:
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        _fail(f'value {value!r} is not a valid boolean')
    return value


# ── public CLI entry points ─────────────────────────────────────


def cmd_init(workdir: Path, task_id: str) -> None:
    '''``loom output init <workdir> --task <id>``.

    Resolves the task's output_schema from plan.yaml, ensures the
    task dir exists, and writes top-level array/object containers
    from the schema.
    '''
    spath = _task_schema_path(workdir, task_id)
    sch = _load_schema_at(spath)
    _ensure_task_dir(workdir, task_id)
    out_path = _task_output_path(workdir, task_id)
    data: dict = _initial_data(sch)
    _atomic_save(out_path, data)
    _emit({'ok': True, 'path': str(out_path), 'schema': str(spath),
           'task': task_id})


def cmd_add(workdir: Path, task_id: str, set_pairs: list[str]) -> None:
    '''``loom output add <workdir> --task <id> --set path=value ...``.

    Applies each ``--set`` pair, validates the result, writes back
    atomically.
    '''
    out_path = _task_output_path(workdir, task_id)
    data = _load_output(out_path)
    schema = _load_schema_at(_task_schema_path(workdir, task_id))

    applied: list[dict] = []
    for pair in set_pairs:
        if '=' not in pair:
            _fail(f'--set requires path=value, got {pair!r}')
        path, _, raw_value = pair.partition('=')
        leaf = _resolve_type_for_path(schema, _split_path(path))
        value = _coerce(raw_value, leaf)
        _set_path(data, path, value)
        applied.append({'path': path,
                        'type': leaf.get('type') if leaf else '?'})

    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        _fail(f'schema violation at {list(e.absolute_path)}: {e.message}',
              applied=applied)

    _atomic_save(out_path, data)
    _emit({'ok': True, 'path': str(out_path), 'task': task_id,
           'applied': applied})

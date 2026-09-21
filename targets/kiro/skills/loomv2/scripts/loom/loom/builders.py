"""Programmatic helpers for `output init` and `output add`.

Consumers: __main__.py CLI dispatch and tests.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from loom.discovery import load_io_yaml
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
    from loom.engine.runner import task_source_folder

    folder = task_source_folder(plan.loom_root, task)
    io = load_io_yaml(folder)
    write_output_yaml(_target_folder(workdir, plan, task_id), _seed_from_schema(io.output_schema))


def output_add(
    workdir: Path, task_id: str, assignments: list[str | tuple[bool, str]]
) -> None:
    """Apply ``path=value`` assignments to output.yaml, coerce, validate, write.

    Paths support dict keys (``meta.tone``), explicit indices
    (``items.0`` or ``items[0]``), list append (``items[]``), and
    last-element addressing (``items[-1]``) — so a list of objects is
    built incrementally: ``items[].name=a`` then ``items[-1].size=3``.

    Each assignment is either a plain ``"path=value"`` string (value
    coerced as a CLI scalar via ``_coerce``) or a ``(is_json, "path=value")``
    tuple from the ``--set-json`` flag: when ``is_json`` is true the
    value is parsed as JSON, so producers can express explicit empty
    values (``[]``, ``""``, ``null``) and nested structures that the
    scalar grammar cannot. Assignments apply in CLI order.

    Validation here is PARTIAL: the document is checked against the
    output schema with ``required`` obligations stripped, so incremental
    multi-call writes are legal while wrong field names
    (``additionalProperties``) and wrong types still fail fast.
    Completeness (all required fields present) is enforced by
    ``runtime complete``.

    For a loop-body task the writes land in the current ``iter-NN/``
    round dir.
    """
    import json

    plan = read_plan_yaml(Path(workdir))
    task = _task(plan, task_id)
    from loom.engine.runner import task_source_folder

    folder = task_source_folder(plan.loom_root, task)
    io = load_io_yaml(folder)
    target_folder = _target_folder(workdir, plan, task_id)
    target = target_folder / "output.yaml"
    doc: Any = yaml.safe_load(target.read_text()) if target.exists() else {}
    for a in assignments:
        is_json, raw = a if isinstance(a, tuple) else (False, a)
        path, _, raw_value = raw.partition("=")
        if is_json:
            try:
                value = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise OutputSchemaError(
                    task_id, f"bad JSON value for {path!r}: {exc}"
                ) from exc
        else:
            value = _coerce(raw_value)
        try:
            _set_by_tokens(doc, _tokenize_path(path), value)
        except ValueError as exc:
            raise OutputSchemaError(task_id, f"bad path {path!r}: {exc}") from exc
    try:
        jsonschema.validate(doc, _without_required(io.output_schema))
    except jsonschema.ValidationError as exc:
        raise OutputSchemaError(task_id, exc.message) from exc
    write_output_yaml(target_folder, doc)


def _task(plan: LoomPlan, task_id: str) -> Task:
    for t in plan.tasks:
        if isinstance(t, Task) and t.id == task_id:
            return t
    raise KeyError(task_id)


# Sentinel token: append a fresh element to a list.
_APPEND = object()

_SEGMENT_RE = re.compile(r"^([^\[\]]*)((?:\[-?\d*\])*)$")
_BRACKET_RE = re.compile(r"\[(-?\d*)\]")


def _tokenize_path(path: str) -> list[Any]:
    """Split a dotted/bracketed path into walk tokens.

    Tokens are str dict keys, int list indices (negative = from the
    end), or the ``_APPEND`` sentinel for ``[]``. A bare numeric dotted
    segment (``items.0``) is an index, matching the historic grammar.
    """
    tokens: list[Any] = []
    for seg in path.split("."):
        m = _SEGMENT_RE.match(seg)
        if not m or (not m.group(1) and not m.group(2)):
            raise ValueError(f"malformed segment {seg!r}")
        head, brackets = m.group(1), m.group(2)
        if head:
            tokens.append(int(head) if head.isdigit() else head)
        elif brackets and seg != brackets:
            raise ValueError(f"malformed segment {seg!r}")
        for b in _BRACKET_RE.findall(brackets):
            tokens.append(_APPEND if b == "" else int(b))
    if not tokens:
        raise ValueError("empty path")
    return tokens


def _seed_for(token: Any) -> Any:
    """Fresh container for an intermediate step, typed by the NEXT token."""
    return [] if (token is _APPEND or isinstance(token, int)) else {}


def _set_by_tokens(doc: Any, tokens: list[Any], value: Any) -> None:
    """Set ``value`` at the location addressed by ``tokens``.

    ``[]`` appends a fresh element; ``[-1]`` (or any negative index)
    addresses from the end of the existing list; non-negative indices
    grow the list as needed.
    """
    cur = doc
    for i, tok in enumerate(tokens):
        last = i == len(tokens) - 1
        if tok is _APPEND or isinstance(tok, int):
            if not isinstance(cur, list):
                raise ValueError(
                    f"list index applied to {type(cur).__name__}"
                )
            if tok is _APPEND:
                cur.append(value if last else _seed_for(tokens[i + 1]))
                if last:
                    return
                cur = cur[-1]
                continue
            idx = tok
            if idx < 0:
                if len(cur) < -idx:
                    raise ValueError(
                        f"index {idx} into list of length {len(cur)}; "
                        "use [] to append first"
                    )
                idx += len(cur)
            while len(cur) <= idx:
                cur.append(None)
            if last:
                cur[idx] = value
                return
            if not isinstance(cur[idx], (dict, list)):
                cur[idx] = _seed_for(tokens[i + 1])
            cur = cur[idx]
        else:
            if not isinstance(cur, dict):
                raise ValueError(
                    f"key {tok!r} applied to {type(cur).__name__}"
                )
            if last:
                cur[tok] = value
                return
            if tok not in cur or not isinstance(cur[tok], (dict, list)):
                cur[tok] = _seed_for(tokens[i + 1])
            cur = cur[tok]


# JSON Schema keywords whose values are themselves schemas (dict), lists
# of schemas, or maps of name → schema. Used by _without_required to
# recurse without ever treating a PROPERTY named "required" as the
# keyword.
_SCHEMA_VALUED = frozenset({
    "items", "additionalProperties", "not", "if", "then", "else",
    "contains", "propertyNames",
})
_SCHEMA_LIST_VALUED = frozenset({"anyOf", "allOf", "oneOf", "prefixItems"})
_SCHEMA_MAP_VALUED = frozenset({
    "properties", "$defs", "definitions", "patternProperties",
    "dependentSchemas",
})


def _without_required(schema: Any) -> Any:
    """Deep-copy ``schema`` with every ``required`` keyword stripped.

    Keeps ``additionalProperties`` / type checks intact so partial
    documents validate structurally while completeness is deferred to
    ``runtime complete``.
    """
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k == "required":
            continue
        if k in _SCHEMA_MAP_VALUED and isinstance(v, dict):
            out[k] = {name: _without_required(sub) for name, sub in v.items()}
        elif k in _SCHEMA_VALUED and isinstance(v, dict):
            out[k] = _without_required(v)
        elif k in _SCHEMA_LIST_VALUED and isinstance(v, list):
            out[k] = [_without_required(x) for x in v]
        else:
            out[k] = v
    return out


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

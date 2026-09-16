"""Mapping resolution: graph.yaml ``input:`` → materialised input.yaml.

Runs at every dispatch (per round for loop bodies). For a Task whose
``input_mapping`` is set, walks the field → placeholder map, resolves
each ``${task:<addr>...}`` reference against the current predicate
context (built from upstream outputs on disk), then STRICTLY validates
the resolved dict against the task's own ``io.yaml/input`` in both
directions — absent required field OR undeclared extra raises
:class:`InputSchemaError`. Missing / unfinished upstream refs raise the
same error (no silent empty-string coercion).

Reserved engine-provided inputs (``__loom``, ``__task``) are handled
here: the mapping MUST NOT wire them (dispatch-time shadow check
raises :class:`InputSchemaError`; the static counterpart is
``loom.validate.mapping.validate_mapping``). After per-field
resolution, the engine merges the reserved values whose names are
declared in ``io.yaml/input.properties`` into the resolved dict, so
``_strict_validate`` sees a union that includes ``__loom`` /
``__task`` and jsonschema deep-validates them against the
author-declared shape (which SHOULD ``$ref`` the meta-schemas).

This is the only place upstream outputs cross into a task; every other
surface (renderer, tool body, agent prompt) reads the task's own
``input.yaml``. Contract-locality is enforced here.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import jmespath
import jsonschema

from loom.engine.models import LoomPlan, Task
from loom.engine.predicate import build_predicate_context, desugar_predicate
from loom.engine.reserved import RESERVED_FIELDS, build_reserved_values
from loom.errors import InputSchemaError


# Full-string ${task:...} placeholder. The mapping RHS is always a
# single placeholder — nothing else is a supported cross-task ref.
_FULL_TASK_REF_RE = re.compile(
    r"^\s*\$\{task:([A-Za-z0-9_\-/]+)"
    r"(?:@([A-Za-z0-9]+))?"
    r"(?::([^}]+))?"
    r"\}\s*$"
)


def resolve_task_input(
    task: Task,
    plan: LoomPlan,
    workdir: Path,
    task_folder: Path,
    input_schema: dict,
) -> dict:
    """Resolve ``task.input_mapping`` and validate the result.

    Args:
      task: The task about to be dispatched. Must have
        ``input_mapping`` set (caller checks for ``None``).
      plan: The composed plan being executed.
      workdir: Absolute path to the run workdir. Used to read upstream
        outputs and to fill ``__loom.workdir``.
      task_folder: Absolute path to the current task's dispatch folder.
        Used to fill ``__task.workdir``.
      input_schema: The task's ``io.yaml/input`` fragment. Validated
        against the resolved dict.

    Returns:
      The materialised input as a JSON-compatible dict. Includes any
      reserved engine-provided fields (``__loom``, ``__task``) whose
      names appear in ``input_schema["properties"]``.

    Raises:
      InputSchemaError: on any of (a) a mapping key that shadows a
        reserved engine-provided name; (b) an upstream ref that cannot
        be resolved because the target task has no completed output
        yet; (c) a resolved dict missing a required field; (d) a
        resolved dict carrying an undeclared field; (e) a jsonschema
        validation failure.
    """
    assert task.input_mapping is not None
    for key in task.input_mapping:
        if key in RESERVED_FIELDS:
            raise InputSchemaError(
                task.id,
                f"input mapping key {key!r} shadows a reserved "
                f"engine-provided name (see references/io.md)",
            )
    ctx = build_predicate_context(plan, workdir)
    resolved: dict[str, Any] = {}
    for field, placeholder in task.input_mapping.items():
        m = _FULL_TASK_REF_RE.match(placeholder)
        if not m:
            raise InputSchemaError(
                task.id,
                f"field {field!r}: mapping value {placeholder!r} is not a "
                "single ${task:...} reference",
            )
        addr = m.group(1)
        expr = desugar_predicate(placeholder.strip())
        try:
            value = jmespath.search(expr, ctx)
        except Exception as exc:  # noqa: BLE001
            raise InputSchemaError(
                task.id,
                f"field {field!r}: could not evaluate {placeholder!r}: {exc}",
            ) from exc
        if value is None:
            raise InputSchemaError(
                task.id,
                f"field {field!r}: upstream ref {placeholder!r} did not "
                f"resolve (task {addr!r} has no completed output)",
            )
        resolved[field] = value

    reserved = build_reserved_values(task, workdir, task_folder)
    declared = input_schema.get("properties") or {}
    for name in RESERVED_FIELDS:
        if name in declared:
            resolved[name] = reserved[name]

    _strict_validate(task.id, resolved, input_schema)
    return resolved


def _strict_validate(task_id: str, doc: dict, schema: dict) -> None:
    """Reject absent required fields, undeclared extras, and schema failures."""
    properties = schema.get("properties") or {}
    required = list(schema.get("required") or [])
    for name in required:
        if name not in doc:
            raise InputSchemaError(
                task_id, f"missing required field {name!r}"
            )
    for key in doc:
        if key not in properties:
            raise InputSchemaError(
                task_id, f"undeclared field {key!r} not in io.yaml/input"
            )
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        raise InputSchemaError(task_id, exc.message) from exc

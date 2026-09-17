"""Mapping resolution: graph.yaml ``input:`` → materialised input.yaml.

Runs at every dispatch (per round for loop bodies). For a Task whose
``input_mapping`` is set, walks the field → placeholder map, resolves
each ``${task:<addr>...}`` reference against the current predicate
context (built from upstream outputs on disk), then STRICTLY validates
the resolved dict against the task's own ``io.yaml/input`` in both
directions — absent required field OR undeclared extra raises
:class:`InputSchemaError`.

Null-vs-unresolved is distinguished per io.md §6 rule 5 (no
engine-inserted defaults):

- The producer task has no completed output at all (``task."addr"``
  or ``task_iter."addr"."sel"`` is ``None`` in the predicate
  context) → :class:`InputSchemaError` — the ref is genuinely
  unresolved.
- The producer output exists but the JMESPath terminal step is
  absent from the producer's ``output.yaml`` (the producer emitted
  ``{}`` where an optional key would live) →
  :class:`InputSchemaError` — undeclared upstream miss.
- The producer output exists AND the terminal step is present but
  its value is literally ``null`` → the null is passed through
  unchanged; the consumer's ``io.yaml/input`` strict validation
  (below) decides whether ``null`` is acceptable, exactly as it
  already does for the round-0 ``@prev`` case.

The round-0 ``@prev`` case is kept as a separate legit-null branch
because ``build_predicate_context`` intentionally leaves ``prev``
absent from ``task_iter."addr"`` on round 0 rather than filling in a
producer-output shape that does not yet exist.

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


# JMESPath path segment: identifier optionally followed by ``[<int>]``
# accessors. Mirrors the projectable subset in ``validate/subtype.py``;
# anything the mapping walk sees outside this shape falls back to
# jmespath.search's evaluation and its None result is treated as
# unresolved (case (b)).
_PATH_SEGMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*)((?:\[\d+\])*)$")
_PATH_INDEX_RE = re.compile(r"\[(\d+)\]")


_SENTINEL = object()  # Distinguishes present-but-null from missing.


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
        reserved engine-provided name; (b) an upstream ref that
        cannot be resolved because the target task has no completed
        output at all; (c) an upstream ref whose JMESPath terminal
        step is absent from the producer's output.yaml; (d) a
        resolved dict missing a required field; (e) a resolved dict
        carrying an undeclared field; (f) a jsonschema validation
        failure.
    """
    assert task.input_mapping is not None
    for key in task.input_mapping:
        if key in RESERVED_FIELDS:
            raise InputSchemaError(
                task.id,
                f"input mapping key {key!r} shadows a reserved "
                f"engine-provided name (see references/io.md)",
            )
    ctx = build_predicate_context(
        plan, workdir, evaluator=(task.id, _folder_round(task_folder))
    )
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
        sel = m.group(2)
        path = m.group(3)
        expr = desugar_predicate(placeholder.strip())
        try:
            value = jmespath.search(expr, ctx)
        except Exception as exc:  # noqa: BLE001
            raise InputSchemaError(
                task.id,
                f"field {field!r}: could not evaluate {placeholder!r}: {exc}",
            ) from exc
        if value is not None:
            resolved[field] = value
            continue
        # jmespath.search returned None. Three distinguishable cases:
        #   (a) producer has no completed output at all — the base of
        #       the projection (``task."addr"`` or
        #       ``task_iter."addr"."sel"``) is ``None`` in ctx.
        #   (b) producer output exists but the JMESPath terminal step
        #       is missing from it.
        #   (c) producer output exists AND the terminal is present but
        #       its value is literally ``null`` — pass through and let
        #       the consumer schema decide.
        # The round-0 ``@prev`` case is a legit-null distinct from
        # any of the above: build_predicate_context deliberately does
        # not set ``per["prev"]`` on round 0, so no producer-output
        # shape is available to probe.
        if sel == "prev" and _folder_round(task_folder) == 0:
            resolved[field] = None
            continue
        base = _producer_base(ctx, addr, sel)
        if base is None:
            raise InputSchemaError(
                task.id,
                f"field {field!r}: upstream ref {placeholder!r} did not "
                f"resolve (task {addr!r} has no completed output)",
            )
        probe = _probe_terminal(base, path)
        if probe is _SENTINEL:
            raise InputSchemaError(
                task.id,
                f"field {field!r}: upstream ref {placeholder!r} did not "
                f"resolve (path {path!r} not present in producer output "
                f"of task {addr!r})",
            )
        # Terminal present, value is null. Pass through unchanged.
        resolved[field] = None

    reserved = build_reserved_values(task, workdir, task_folder)
    declared = input_schema.get("properties") or {}
    for name in RESERVED_FIELDS:
        if name in declared:
            resolved[name] = reserved[name]

    _strict_validate(task.id, resolved, input_schema)
    return resolved


def _producer_base(ctx: dict, addr: str, sel: str | None) -> Any:
    """Return the producer output dict (or None) for ``addr``[@``sel``].

    ``None`` means "no completed output available" — case (a). A dict
    (possibly empty) means the producer has output; caller walks the
    JMESPath path against it.
    """
    if sel is None:
        return ctx.get("task", {}).get(addr)
    per = ctx.get("task_iter", {}).get(addr) or {}
    if sel == "prev":
        return per.get("prev")
    # Numeric selector: normalise ``@05`` to ``"5"`` to match the
    # str(int) keys built in build_predicate_context.
    key = str(int(sel)) if sel.isdigit() else sel
    return per.get(key)


def _probe_terminal(base: Any, path: str | None) -> Any:
    """Walk ``path`` in ``base``; return the terminal value or ``_SENTINEL``.

    ``_SENTINEL`` signals "terminal step is absent from the producer's
    output" — case (b). A returned value of ``None`` (only reachable
    when the walk lands on a key whose stored value is literally
    ``None``) is case (c) — pass-through null.

    Falls back to ``_SENTINEL`` on any JMESPath fragment outside the
    projectable subset (identifier + dot + integer bracket-index) so
    the exotic-JMESPath dispatch stays fail-closed at runtime, matching
    the static ``validate/subtype`` policy.
    """
    if not path:
        return base
    current = base
    segments = path.split(".")
    for seg in segments:
        m = _PATH_SEGMENT_RE.match(seg)
        if not m:
            return _SENTINEL
        name = m.group(1)
        indices = [int(i) for i in _PATH_INDEX_RE.findall(m.group(2) or "")]
        if not isinstance(current, dict) or name not in current:
            return _SENTINEL
        current = current[name]
        for idx in indices:
            if current is None:
                return _SENTINEL
            if not isinstance(current, list) or idx >= len(current):
                return _SENTINEL
            current = current[idx]
    return current


def _folder_round(task_folder: Path) -> int | None:
    """Round index of a dispatch folder (``iter-NN``), or None if flat."""
    name = task_folder.name
    if name.startswith("iter-") and name[len("iter-"):].isdigit():
        return int(name[len("iter-"):])
    return None


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

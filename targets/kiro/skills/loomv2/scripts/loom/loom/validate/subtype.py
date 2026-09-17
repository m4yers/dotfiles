"""Sound producer/consumer alignment: subtype projection + required wiring.

Two static passes wired into ``_lifecycle._static_validate`` after
:func:`loom.validate.references.validate_references`. Both consume the
placeholder parse surfaced by :func:`loom.validate.references.iter_task_refs`
and read io.yaml schemas via :class:`loom.validate.schemas.SchemaCache`,
so producer / consumer schema lookups honour the same
``source_root``-based re-anchoring the reference check already uses for
inlined subgraph tasks.

Soundness goal (see references/io.md §6): if static validation passes
at ``$LOOM runtime init`` AND every producer satisfies its own
``io.yaml/output``, then every consumer's materialised ``input.yaml``
satisfies its ``io.yaml/input`` at dispatch — with zero engine-inserted
defaults.

- :func:`validate_subtype` — for every ``input_mapping`` entry
  ``field: ${task:X[@sel][:PATH]}``, project ``PATH`` through task
  ``X``'s output schema (propagating a may-be-absent presence bit on
  optional-chain steps, array wildcards/filters, and ``@prev`` on
  round 0) and check the projected schema is a subtype of the
  consumer's ``io.yaml/input.properties[field]`` schema. Static
  ambiguity fails closed with :class:`TypeMismatchError`.

- :func:`validate_required_wiring` — every consumer
  ``io.yaml/input.required`` name (except reserved
  ``__loom``/``__task``) must be wired in ``input_mapping``. Entry
  tasks seeded by ``runtime init --set`` (no ``input_mapping``) are
  exempt because that seeding path is strict-validated at init.

Failures preserve the "nothing written on failure" invariant of the
init/extend lifecycle because both passes run before any workdir writes.
"""
from __future__ import annotations

import re
from typing import Any

from loom.engine.models import LoomPlan, Task
from loom.engine.reserved import RESERVED_FIELDS
from loom.errors import SchemaError, TypeMismatchError
from loom.validate.references import iter_task_refs
from loom.validate.schemas import SchemaCache


# Path segment: identifier optionally followed by any number of
# ``[<integer>]`` index accessors. Anything else — filters, wildcards,
# functions, string keys with quotes, arithmetic — is deliberately
# outside the statically-projectable subset and fails closed.
_SEGMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*)((?:\[\d+\])*)$")
_INDEX_RE = re.compile(r"\[(\d+)\]")


# JSON Schema keys that carry conditional / negation semantics we cannot
# statically project through soundly. Presence on the producer side of a
# projection step forces fail-closed.
_AMBIGUOUS_KEYS = frozenset({"not", "if", "then", "else"})


def validate_subtype(plan: LoomPlan) -> None:
    """Reject ``input_mapping`` wirings that fail static subtype projection.

    For every task with an ``input_mapping``, parse each placeholder
    into (address, jmespath, selector), project the producer's
    ``io.yaml/output`` through the jmespath, and check the projected
    schema is a subtype of the consumer's ``io.yaml/input.properties[field]``
    schema. Fails closed with :class:`TypeMismatchError` on any static
    ambiguity — JMESPath filters/wildcards/functions, ``not`` /
    ``if`` / ``then`` / ``else`` on the projection path, or oneOf
    branches on the producer that can match with different projected
    shapes.
    """
    cache = SchemaCache()
    tasks = [t for t in plan.tasks if isinstance(t, Task)]
    by_id = {t.id: t for t in tasks}
    for consumer in tasks:
        if not consumer.input_mapping:
            continue
        consumer_schema = _schema_for(cache, plan, consumer).input_schema
        consumer_props = consumer_schema.get("properties") or {}
        consumer_required = set(consumer_schema.get("required") or [])
        for field, placeholder in consumer_mapping_items(consumer):
            refs = list(iter_task_refs(placeholder))
            if len(refs) != 1:
                # Zero refs isn't a task ref; the strict FULL match is
                # enforced at dispatch. Multi-ref mapping values are not
                # supported by the placeholder grammar; leave the runtime
                # to reject with InputSchemaError. Static subtype has
                # nothing sound to say.
                continue
            addr, jmespath, selector = refs[0]
            producer = by_id.get(addr)
            if producer is None:
                # Unknown-task refs are already rejected by
                # validate_references before we run.
                continue
            producer_schema = _schema_for(cache, plan, producer).output_schema
            consumer_field_schema = consumer_props.get(field)
            if consumer_field_schema is None:
                # Undeclared consumer field is caught by dispatch-time
                # strict validation (undeclared field). Nothing sound to
                # say statically about a field the consumer schema does
                # not know.
                continue
            projected, may_be_absent = _project(
                producer_schema, jmespath, selector,
                producer_id=addr, consumer_id=consumer.id, field=field,
                placeholder=placeholder,
            )
            _check_subtype(
                projected, consumer_field_schema,
                may_be_absent=may_be_absent,
                required=field in consumer_required,
                producer_id=addr, consumer_id=consumer.id,
                field=field, placeholder=placeholder,
            )


def validate_required_wiring(plan: LoomPlan) -> None:
    """Reject consumers whose ``io.yaml/input.required`` fields are unwired.

    Every task with an ``input_mapping`` must wire every name in its
    ``io.yaml/input.required`` list, except reserved names
    (``__loom`` / ``__task``, engine-provided) and, implicitly, the
    entry task seeded via ``runtime init --set`` (which has no
    ``input_mapping`` at all).
    """
    cache = SchemaCache()
    for consumer in plan.tasks:
        if not isinstance(consumer, Task):
            continue
        if consumer.input_mapping is None:
            # Entry-task pattern: caller-seeded, strict-validated by
            # `runtime init --set`. Nothing to check here.
            continue
        consumer_schema = _schema_for(cache, plan, consumer).input_schema
        required = list(consumer_schema.get("required") or [])
        wired = set(consumer.input_mapping.keys())
        for name in required:
            if name in RESERVED_FIELDS:
                # Engine-filled; author does not wire it.
                continue
            if name in wired:
                continue
            raise SchemaError(
                f"task {consumer.id!r}: io.yaml/input.required field "
                f"{name!r} is not wired in graph.yaml input_mapping "
                "(and is not a reserved engine-provided name)"
            )


# ---- helpers ----------------------------------------------------------


def consumer_mapping_items(task: Task):
    """Yield ``(field, placeholder)`` for every non-reserved mapping entry."""
    for field, placeholder in (task.input_mapping or {}).items():
        # ReservedShadowError already rejects reserved keys in
        # validate_mapping; skip them here so the subtype pass is
        # order-independent w.r.t. the ordering of validators.
        if field in RESERVED_FIELDS:
            continue
        yield field, placeholder


def _schema_for(cache: SchemaCache, plan: LoomPlan, task: Task):
    """Load a task's cached io.yaml through the shared schema cache.

    Inlined subgraph tasks re-anchor through ``source_root`` so we read
    the child skill's io.yaml, not the composed plan's root.
    """
    root_for_target = (
        task.source_root if task.source_root is not None else plan.loom_root
    )
    return cache.get(root_for_target, task.id)


def _project(
    schema: dict,
    jmespath: str | None,
    selector: str | None,
    *,
    producer_id: str,
    consumer_id: str,
    field: str,
    placeholder: str,
) -> tuple[dict, bool]:
    """Walk ``jmespath`` through ``schema``; return (projected, may_be_absent).

    Marks ``may_be_absent`` when:

    - the selector is ``@prev`` (nullable on round 0), or
    - any walked step lands on a non-required property, or
    - any array index may fall outside ``minItems`` guarantees.

    Fails closed on any of:

    - JMESPath segments outside ``identifier(\\[<int>\\])*``
      (filters, wildcards, functions, quoted keys).
    - schemas with ``not`` / ``if`` / ``then`` / ``else``.
    - producer-side ``oneOf`` where more than one branch admits the
      next step (statically indistinguishable projections).
    """
    may_be_absent = selector == "prev"
    current = schema
    if not jmespath:
        return current, may_be_absent
    segments = jmespath.split(".")
    for seg in segments:
        current, seg_absent = _project_segment(
            current, seg,
            producer_id=producer_id, consumer_id=consumer_id,
            field=field, placeholder=placeholder,
        )
        if seg_absent:
            may_be_absent = True
    return current, may_be_absent


def _project_segment(
    schema: dict,
    segment: str,
    *,
    producer_id: str,
    consumer_id: str,
    field: str,
    placeholder: str,
) -> tuple[dict, bool]:
    """Project one dotted segment (possibly with ``[<int>]`` indices)."""
    if not isinstance(schema, dict):
        _fail(
            "producer schema is not a JSON Schema object; cannot project",
            producer_id, placeholder, consumer_id, field,
        )
    _reject_ambiguous_keys(schema, producer_id, placeholder, consumer_id, field)
    schema = _select_single_branch(
        schema, segment,
        producer_id=producer_id, consumer_id=consumer_id,
        field=field, placeholder=placeholder,
    )
    m = _SEGMENT_RE.match(segment)
    if not m:
        _fail(
            f"JMESPath segment {segment!r} outside the statically-"
            f"projectable subset (identifier(.identifier)*(\\[<int>\\])*)",
            producer_id, placeholder, consumer_id, field,
        )
    name = m.group(1)
    indices = [int(idx) for idx in _INDEX_RE.findall(m.group(2) or "")]
    may_be_absent = False
    # Step through the identifier.
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if name not in props:
        _fail(
            f"producer schema has no property {name!r} at this point; "
            "cannot project soundly",
            producer_id, placeholder, consumer_id, field,
        )
    current = props[name]
    if name not in required:
        may_be_absent = True
    # Step through any ``[<int>]`` indices on this segment.
    for idx in indices:
        _reject_ambiguous_keys(
            current, producer_id, placeholder, consumer_id, field,
        )
        items = current.get("items")
        if not isinstance(items, dict):
            _fail(
                f"array items at index {idx} not a single schema (only "
                "homogeneous ``items: <schema>`` is projectable)",
                producer_id, placeholder, consumer_id, field,
            )
        min_items = current.get("minItems", 0)
        if idx >= min_items:
            may_be_absent = True
        current = items
    return current, may_be_absent


def _reject_ambiguous_keys(
    schema: dict,
    producer_id: str,
    placeholder: str,
    consumer_id: str,
    field: str,
) -> None:
    """Fail closed if a schema uses ``not`` / ``if`` / ``then`` / ``else``."""
    if not isinstance(schema, dict):
        return
    for key in _AMBIGUOUS_KEYS:
        if key in schema:
            _fail(
                f"producer schema uses {key!r}; static projection cannot "
                "reason through conditional/negation subschemas",
                producer_id, placeholder, consumer_id, field,
            )


def _select_single_branch(
    schema: dict,
    segment: str,
    *,
    producer_id: str,
    consumer_id: str,
    field: str,
    placeholder: str,
) -> dict:
    """If ``schema`` carries ``oneOf`` / ``anyOf``, pick the sole branch
    that admits ``segment``; fail closed on multi-branch ambiguity.
    """
    for key in ("oneOf", "anyOf"):
        branches = schema.get(key)
        if not branches:
            continue
        # Identify branches that have the property named by segment's
        # identifier prefix.
        m = _SEGMENT_RE.match(segment)
        if not m:
            _fail(
                f"cannot project segment {segment!r} through {key} branches",
                producer_id, placeholder, consumer_id, field,
            )
        name = m.group(1)
        admitting = [
            b for b in branches
            if isinstance(b, dict)
            and name in (b.get("properties") or {})
        ]
        if len(admitting) != 1:
            _fail(
                f"producer schema {key} has {len(admitting)} branches "
                f"admitting property {name!r}; static projection requires "
                "exactly one to be sound",
                producer_id, placeholder, consumer_id, field,
            )
        # Merge the chosen branch into the outer schema's required/props
        # so the caller can walk the field.
        merged = dict(schema)
        merged.pop(key, None)
        picked = admitting[0]
        merged_props = dict(merged.get("properties") or {})
        merged_props.update(picked.get("properties") or {})
        merged["properties"] = merged_props
        merged_required = set(merged.get("required") or []) | set(
            picked.get("required") or []
        )
        merged["required"] = sorted(merged_required)
        return merged
    return schema


def _check_subtype(
    projected: dict,
    consumer_field: dict,
    *,
    may_be_absent: bool,
    required: bool,
    producer_id: str,
    consumer_id: str,
    field: str,
    placeholder: str,
) -> None:
    """Assert projected is a subtype of consumer_field."""
    # Nullability requirement when the projection may resolve to null:
    # a required consumer field whose schema doesn't accept null cannot
    # legally receive an absent-shaped projection.
    if may_be_absent and required and not _accepts_null(consumer_field):
        _fail(
            "producer projection may be absent (null) but consumer field "
            "is required and does not accept null",
            producer_id, placeholder, consumer_id, field,
        )
    ok, reason = _is_subtype(projected, consumer_field, may_be_absent)
    if not ok:
        _fail(reason, producer_id, placeholder, consumer_id, field)


def _is_subtype(
    p: dict,
    c: dict,
    may_be_absent: bool,
) -> tuple[bool, str]:
    """Return ``(True, "")`` if ``p`` is a subtype of ``c``, else ``(False, reason)``.

    Fails closed on ambiguity by returning ``False``.
    """
    if not isinstance(p, dict) or not isinstance(c, dict):
        return False, "projected or consumer schema is not a JSON Schema object"
    for schema in (p, c):
        for key in _AMBIGUOUS_KEYS:
            if key in schema:
                return False, (
                    f"schema uses {key!r}; static subtyping cannot "
                    "reason through conditional/negation subschemas"
                )
    # Union on producer: every branch must subtype consumer (or one of
    # its branches).
    p_branches = p.get("oneOf") or p.get("anyOf")
    if p_branches:
        c_branches = c.get("oneOf") or c.get("anyOf") or [c]
        for pb in p_branches:
            if not any(_is_subtype(pb, cb, may_be_absent)[0] for cb in c_branches):
                return False, "producer union branch matches no consumer branch"
        return True, ""
    # Union on consumer only: producer must subtype at least one branch.
    c_branches = c.get("oneOf") or c.get("anyOf")
    if c_branches:
        if any(_is_subtype(p, cb, may_be_absent)[0] for cb in c_branches):
            return True, ""
        return False, "producer matches no consumer union branch"
    # type-set inclusion (with may-be-absent injecting null into the
    # producer's type set).
    p_types = _type_set(p)
    if may_be_absent and p_types is not None:
        p_types = p_types | {"null"}
    c_types = _type_set(c)
    if p_types is not None and c_types is not None:
        if not p_types.issubset(c_types):
            return False, (
                f"producer types {sorted(p_types)} not subset of consumer "
                f"types {sorted(c_types)}"
            )
    elif may_be_absent and c_types is not None and "null" not in c_types:
        # Producer has no explicit type but may be absent; consumer must
        # accept null.
        return False, (
            f"producer projection may be null but consumer types "
            f"{sorted(c_types)} do not include null"
        )
    # enum subset: any enum on producer must be a subset of any enum on
    # consumer.
    if "enum" in c:
        c_enum = c["enum"]
        if "enum" in p:
            if not set(_hashable(v) for v in p["enum"]).issubset(
                set(_hashable(v) for v in c_enum)
            ):
                return False, "producer enum not a subset of consumer enum"
        elif "const" in p:
            if _hashable(p["const"]) not in set(_hashable(v) for v in c_enum):
                return False, "producer const not in consumer enum"
        else:
            return False, (
                "consumer restricts to enum but producer has no enum/const"
            )
    # const equality.
    if "const" in c:
        if p.get("const") != c["const"]:
            return False, "producer const does not equal consumer const"
    # numeric bound tightening: producer's admitted range must sit
    # inside consumer's admitted range.
    for key, cmp in (("minimum", 1), ("exclusiveMinimum", 1)):
        if key in c:
            if key not in p or p[key] < c[key]:
                return False, f"producer {key!r} does not tighten consumer bound"
    for key in ("maximum", "exclusiveMaximum"):
        if key in c:
            if key not in p or p[key] > c[key]:
                return False, f"producer {key!r} does not tighten consumer bound"
    # object: required-superset + covariant properties + additionalProperties.
    if _matches_type(c_types, "object") and _matches_type(p_types, "object"):
        p_required = set(p.get("required") or [])
        c_required = set(c.get("required") or [])
        if not c_required.issubset(p_required):
            missing = sorted(c_required - p_required)
            return False, (
                f"producer required {sorted(p_required)} missing consumer-required "
                f"{missing}"
            )
        c_props = c.get("properties") or {}
        p_props = p.get("properties") or {}
        for name, c_prop in c_props.items():
            if name in p_props:
                ok, reason = _is_subtype(p_props[name], c_prop, False)
                if not ok:
                    return False, f"property {name!r}: {reason}"
        if c.get("additionalProperties") is False:
            if p.get("additionalProperties") is not False:
                return False, (
                    "consumer forbids additionalProperties but producer "
                    "does not"
                )
    # array: covariant items + tightened min/max.
    if _matches_type(c_types, "array") and _matches_type(p_types, "array"):
        c_items = c.get("items")
        p_items = p.get("items")
        if isinstance(c_items, dict) and isinstance(p_items, dict):
            ok, reason = _is_subtype(p_items, c_items, False)
            if not ok:
                return False, f"array items: {reason}"
        elif isinstance(c_items, dict) and p_items is None:
            return False, "consumer constrains array items; producer does not"
        if "minItems" in c and p.get("minItems", 0) < c["minItems"]:
            return False, "producer minItems does not tighten consumer bound"
        if "maxItems" in c and p.get("maxItems", float("inf")) > c["maxItems"]:
            return False, "producer maxItems does not tighten consumer bound"
    return True, ""


def _accepts_null(schema: dict) -> bool:
    """Whether ``schema`` accepts a JSON null."""
    if not isinstance(schema, dict):
        return False
    if schema.get("type") == "null":
        return True
    t = schema.get("type")
    if isinstance(t, list) and "null" in t:
        return True
    if schema.get("const") is None and "const" in schema:
        return True
    if "enum" in schema and None in schema["enum"]:
        return True
    for key in ("oneOf", "anyOf"):
        branches = schema.get(key)
        if branches and any(
            isinstance(b, dict) and _accepts_null(b) for b in branches
        ):
            return True
    return False


def _type_set(schema: dict) -> set[str] | None:
    """Set of ``type`` values accepted by ``schema``; ``None`` if untyped."""
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if t is None:
        return None
    if isinstance(t, str):
        return {t}
    if isinstance(t, list):
        return set(t)
    return None


def _matches_type(type_set: set[str] | None, wanted: str) -> bool:
    return type_set is not None and wanted in type_set


def _hashable(value: Any) -> Any:
    """Coerce a JSON-shaped value into something ``set`` can hold."""
    if isinstance(value, (list, dict)):
        # Deep-freeze via repr — enum values are typically scalars, so
        # this branch is rarely hit but keeps the code total.
        return repr(value)
    return value


def _fail(
    reason: str,
    producer_id: str,
    placeholder: str,
    consumer_id: str,
    field: str,
) -> None:
    """Raise :class:`TypeMismatchError` naming the wiring triple."""
    raise TypeMismatchError(
        f"input_mapping wiring "
        f"producer={producer_id!r} placeholder={placeholder!r} → "
        f"consumer={consumer_id!r} field={field!r}: {reason}"
    )

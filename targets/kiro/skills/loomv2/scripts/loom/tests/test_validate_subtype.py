"""Static subtype-projection and required-wiring validators.

Covers ``loom.validate.subtype.validate_subtype`` and
``loom.validate.subtype.validate_required_wiring``. Both passes run
during ``$LOOM runtime init`` and MUST catch producer/consumer
alignment defects before any workdir writes (io.md §6b).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom import init
from loom.__main__ import main
from loom.errors import SchemaError, TypeMismatchError


# ---- shared task-writing helpers -------------------------------------


def _write_tool_task(
    folder: Path, name: str, input_schema, output_schema, body: str = ""
) -> None:
    """Write a minimal tool task folder (io.yaml, io_types.py, tool.py)."""
    from loom.naming import pascal_case_task_name

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": input_schema,
        "output": output_schema,
    }))
    pascal = pascal_case_task_name(name)
    fields_in = list(input_schema.get("properties", {}).keys())
    fields_out = list(output_schema.get("properties", {}).keys())

    lines = [
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit",
        "from dataclasses import dataclass",
        "from typing import ClassVar",
        "",
        "",
        "@dataclass",
        f"class {pascal}Input:",
        "    VERSION: ClassVar[int] = 1",
    ]
    for f in fields_in:
        lines.append(f"    {f}: int = None  # test stub — real gen types per JSON schema")
    if not fields_in:
        lines.append("    pass")
    lines += [
        "    @classmethod",
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {fields_in!r}}})",
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {fields_in!r}}}",
        "",
        "",
        "@dataclass",
        f"class {pascal}Output:",
        "    VERSION: ClassVar[int] = 1",
    ]
    for f in fields_out:
        lines.append(f"    {f}: int = None")
    if not fields_out:
        lines.append("    pass")
    lines += [
        "    @classmethod",
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {fields_out!r}}})",
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {fields_out!r}}}",
    ]
    (folder / "io_types.py").write_text("\n".join(lines) + "\n")
    (folder / "tool.py").write_text(
        body
        or f"from io_types import {pascal}Input, {pascal}Output\n"
        f"def {name.replace('-', '_')}(inp: {pascal}Input) -> {pascal}Output:\n"
        f"    return {pascal}Output()\n"
    )


def _build_two_task_loom(
    tmp_path: Path,
    seed_output: dict,
    target_input: dict,
    wire: str = "${task:seed:field}",
    field_name: str = "field",
) -> tuple[Path, Path]:
    """Build a two-task loom (seed → target) with the given schemas."""
    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        seed_output,
    )
    _write_tool_task(
        root / "target", "target",
        target_input,
        {"type": "object", "additionalProperties": False},
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "target", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"],
             "input": {field_name: wire}},
        ],
    }))
    workdir = tmp_path / "run"
    return root, workdir


# ---- validate_subtype: basic type match / mismatch -------------------


def test_subtype_matching_types_pass(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


def test_subtype_type_mismatch_raises(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "string"}},
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError) as exc:
        init(workdir, loom_root=root)
    message = str(exc.value)
    assert "'seed'" in message and "'target'" in message and "'field'" in message


# ---- enum subset ------------------------------------------------------


def test_subtype_enum_subset_passes(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "string", "enum": ["a", "b"]}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "string", "enum": ["a", "b", "c"]}},
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


def test_subtype_enum_not_subset_raises(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "string", "enum": ["a", "b", "c"]}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "string", "enum": ["a", "b"]}},
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


# ---- const equality ---------------------------------------------------


def test_subtype_const_equality_passes(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"const": 42}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"const": 42}},
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


def test_subtype_const_inequality_raises(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"const": 42}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"const": 43}},
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


# ---- numeric-bound tightening ----------------------------------------


def test_subtype_numeric_bounds_tighten_passes(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "integer", "minimum": 5, "maximum": 8,
            }},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "integer", "minimum": 0, "maximum": 10,
            }},
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


def test_subtype_numeric_bounds_widen_raises(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "integer", "minimum": 0,
            }},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "integer", "minimum": 5,
            }},
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


# ---- object: required-superset + covariant properties ---------------


def test_subtype_object_required_superset_passes(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
            },
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"a": {"type": "integer"}},
                    "required": ["a"],
                },
            },
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


def test_subtype_object_required_missing_raises(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"a": {"type": "integer"}},
                    "required": ["a"],
                },
            },
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
            },
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


# ---- array covariance + tightening -----------------------------------


def test_subtype_array_items_covariant_passes(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "array",
                "items": {"type": "integer", "minimum": 5},
                "minItems": 3, "maxItems": 5,
            }},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 1, "maxItems": 10,
            }},
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


def test_subtype_array_items_broaden_raises(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "array",
                "items": {"type": "integer"},
            }},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "array",
                "items": {"type": "string"},
            }},
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


# ---- union branch matching -------------------------------------------


def test_subtype_producer_union_all_branches_match_consumer(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "anyOf": [
                    {"type": "integer", "minimum": 5},
                    {"type": "integer", "maximum": 3},
                ],
            }},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
    )
    init(workdir, loom_root=root)


# ---- @prev nullable on round 0 --------------------------------------


def test_subtype_prev_projection_requires_nullable_consumer(tmp_path: Path):
    """A `@prev` projection is nullable on round 0; a required consumer
    field that does NOT accept null fails the subtype check."""
    root = tmp_path / "loom"
    root.mkdir()
    (root / "form").mkdir()
    (root / "form" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"hint": {"type": "string"}},
            "required": ["hint"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
    }))
    (root / "form" / "prompt.md.j2").write_text("{{ input.hint }}\n")
    (root / "verdict").mkdir()
    (root / "verdict" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"hint": {"type": "string"}},
            "required": ["hint"],
        },
    }))
    (root / "verdict" / "prompt.md.j2").write_text("form-verdict\n")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "form", "kind": "agent", "version": 1,
             "input": {"hint": "${task:verdict@prev:hint}"}},
            {"id": "verdict", "kind": "agent", "version": 1,
             "depends_on_all": ["form"]},
        ],
        "latches": [{"task": "verdict", "header": "form", "fuel": 5}],
    }))
    workdir = tmp_path / "run"
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


def test_subtype_prev_projection_accepts_nullable_consumer(tmp_path: Path):
    """A `@prev` projection is nullable on round 0; when the consumer
    field types include ``null`` (or is not required), subtype passes."""
    root = tmp_path / "loom"
    root.mkdir()
    (root / "form").mkdir()
    (root / "form" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"hint": {"type": ["string", "null"]}},
            "required": ["hint"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
    }))
    (root / "form" / "prompt.md.j2").write_text("{{ input.hint }}\n")
    (root / "verdict").mkdir()
    (root / "verdict" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"hint": {"type": "string"}},
            "required": ["hint"],
        },
    }))
    (root / "verdict" / "prompt.md.j2").write_text("form-verdict\n")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "form", "kind": "agent", "version": 1,
             "input": {"hint": "${task:verdict@prev:hint}"}},
            {"id": "verdict", "kind": "agent", "version": 1,
             "depends_on_all": ["form"]},
        ],
        "latches": [{"task": "verdict", "header": "form", "fuel": 5}],
    }))
    workdir = tmp_path / "run"
    init(workdir, loom_root=root)


# ---- fail-closed on JMESPath filters / wildcards / functions -------


def test_subtype_jmespath_wildcard_fails_closed(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"items": {
                "type": "array",
                "items": {"type": "object",
                          "additionalProperties": False,
                          "properties": {"x": {"type": "integer"}}},
            }},
            "required": ["items"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "array", "items": {"type": "integer"},
            }},
            "required": ["field"],
        },
        wire="${task:seed:items[*].x}",  # wildcard [*]: fail-closed.
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


def test_subtype_jmespath_filter_fails_closed(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"items": {
                "type": "array",
                "items": {"type": "object",
                          "additionalProperties": False,
                          "properties": {"x": {"type": "integer"}}},
            }},
            "required": ["items"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
        wire="${task:seed:items[?x > `5`].x}",
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


def test_subtype_ambiguous_not_fails_closed(tmp_path: Path):
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {
                "type": "integer",
                "not": {"const": 0},
            }},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
    )
    with pytest.raises(TypeMismatchError):
        init(workdir, loom_root=root)


# ---- validate_required_wiring ---------------------------------------


def test_required_wiring_missing_field_flagged(tmp_path: Path):
    """A consumer's io.yaml/input.required field with no wiring key in
    graph.yaml raises :class:`SchemaError` at ``$LOOM runtime init``."""
    root, workdir = _build_two_task_loom(
        tmp_path,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field": {"type": "integer"},
                "extra": {"type": "integer"},
            },
            "required": ["field", "extra"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "field": {"type": "integer"},
                "extra": {"type": "integer"},
            },
            "required": ["field", "extra"],
        },
    )
    # graph.yaml wires only `field`, leaving required `extra` unwired.
    with pytest.raises(SchemaError):
        init(workdir, loom_root=root)


def test_required_wiring_reserved_fields_never_flagged(tmp_path: Path):
    """Reserved engine-provided names (``__loom``, ``__task``) are
    filled by the engine and MUST NOT be flagged as missing wiring
    even when required in the consumer's io.yaml."""
    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    )
    (root / "ask").mkdir()
    (root / "ask" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "n": {"type": "integer"},
                "__loom": {},
                "__task": {},
            },
            "required": ["n", "__loom", "__task"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"reply": {"type": "string"}},
            "required": ["reply"],
        },
    }))
    (root / "ask" / "prompt.md.j2").write_text(
        "{{ input.n }}@{{ input.__loom.workdir }}\n"
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "ask", "kind": "agent", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"n": "${task:seed:n}"}},
        ],
    }))
    workdir = tmp_path / "run"
    # No SchemaError: __loom/__task are reserved.
    init(workdir, loom_root=root)


def test_required_wiring_entry_task_exempt_when_no_mapping(tmp_path: Path):
    """An entry task with NO ``input:`` mapping in graph.yaml is
    seeded via ``runtime init --set`` (or hand-authored input.yaml);
    the required-wiring pass has nothing to check because
    ``input_mapping is None`` — skipped."""
    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"m": {"type": "integer"}},
            "required": ["m"],
        },
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
        ],
    }))
    workdir = tmp_path / "run"
    init(workdir, loom_root=root)


# ---- subgraph source_root re-anchoring ------------------------------


def test_subtype_subgraph_inlined_task_reads_child_schema(tmp_path: Path):
    """A subgraph-inlined child task's io.yaml lives under the CHILD
    skill root, not the composed plan root; the subtype pass must
    re-anchor via ``source_root`` (same as ``validate_references``)."""
    # Child: one task `child-lint` with matching integer schema.
    child = tmp_path / "child" / "loom"
    _write_tool_task(
        child / "child-lint", "child-lint",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"field": {"type": "integer"}},
            "required": ["field"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    )
    (child / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "child-lint", "kind": "tool", "version": 1}],
    }))
    parent = tmp_path / "parent" / "loom"
    _write_tool_task(
        parent / "origin", "origin",
        {"type": "object", "additionalProperties": False},
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    )
    (parent / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "origin", "kind": "tool", "version": 1},
            {"id": "instance", "kind": "subgraph", "version": 1,
             "root": "../../child/loom",
             "depends_on_all": ["origin"],
             "input": {"field": "${task:origin:n}"}},
        ],
    }))
    workdir = tmp_path / "run"
    init(workdir, loom_root=parent)

"""Static validation of Jinja templates and graph.yaml input mappings.

Covers ``loom.validate.templates.validate_templates`` and
``loom.validate.mapping.validate_mapping`` — the two validators wired
into ``_lifecycle._static_validate`` so ``$LOOM validate`` and
``$LOOM runtime init`` reject offending plans before any workdir
write.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.engine.models import LoomPlan, Task
from loom.errors import ReservedShadowError, TemplateReferenceError
from loom.validate.mapping import validate_mapping
from loom.validate.templates import validate_templates


# ---- fixtures ----------------------------------------------------------

def _agent_task_folder(
    loom_root: Path,
    name: str,
    *,
    input_schema: dict,
    template: str,
) -> Path:
    """Author an agent task folder under ``loom_root``."""
    folder = loom_root / name
    folder.mkdir(parents=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": input_schema,
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"summary": {"type": "string"}},
            "required": ["summary"],
        },
    }))
    (folder / "prompt.md.j2").write_text(template)
    return folder


def _plan_with_agent(loom_root: Path, task_id: str) -> LoomPlan:
    """Minimal LoomPlan carrying one agent Task named ``task_id``."""
    return LoomPlan(
        loom_root=loom_root,
        tasks=[Task(id=task_id, kind="agent")],
    )


# ---- validate_templates ------------------------------------------------

def test_top_level_identifier_rejected(tmp_path: Path):
    loom_root = tmp_path / "loom"
    _agent_task_folder(
        loom_root,
        "ask",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        template="{{ foo }}",
    )
    with pytest.raises(TemplateReferenceError) as exc:
        validate_templates(_plan_with_agent(loom_root, "ask"))
    assert "foo" in str(exc.value)


def test_input_attr_not_declared_rejected(tmp_path: Path):
    loom_root = tmp_path / "loom"
    _agent_task_folder(
        loom_root,
        "ask",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"foo": {"type": "string"}},
            "required": ["foo"],
        },
        template="{{ input.bar }}",
    )
    with pytest.raises(TemplateReferenceError) as exc:
        validate_templates(_plan_with_agent(loom_root, "ask"))
    assert "input.bar" in str(exc.value)


def test_reserved_loom_via_input_accepted(tmp_path: Path):
    loom_root = tmp_path / "loom"
    _agent_task_folder(
        loom_root,
        "ask",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"__loom": {}},
            "required": ["__loom"],
        },
        template="{{ input.__loom.workdir }}",
    )
    validate_templates(_plan_with_agent(loom_root, "ask"))  # no raise


def test_reserved_loom_unknown_attr_rejected(tmp_path: Path):
    loom_root = tmp_path / "loom"
    _agent_task_folder(
        loom_root,
        "ask",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"__loom": {}},
            "required": ["__loom"],
        },
        template="{{ input.__loom.bogus }}",
    )
    with pytest.raises(TemplateReferenceError) as exc:
        validate_templates(_plan_with_agent(loom_root, "ask"))
    assert "input.__loom.bogus" in str(exc.value)


def test_reserved_task_narrowing_rejects_dropped_field(tmp_path: Path):
    """Under the bare-declaration design the loader always substitutes
    the canonical ``__task`` meta-schema; author narrowing is no longer
    possible. A template referencing an attribute NOT in the canonical
    schema (e.g. ``status``) is still rejected by the template
    validator — the check now runs against the substituted meta-schema
    rather than a narrowed inline shape."""
    loom_root = tmp_path / "loom"
    _agent_task_folder(
        loom_root,
        "ask",
        input_schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {"__task": {}},
            "required": ["__task"],
        },
        template="{{ input.__task.status }}",
    )
    with pytest.raises(TemplateReferenceError) as exc:
        validate_templates(_plan_with_agent(loom_root, "ask"))
    assert "input.__task.status" in str(exc.value)


# ---- validate_mapping --------------------------------------------------

def test_reserved_shadow_static(tmp_path: Path):
    """Direct call: mapping wires ``__loom`` — raises ReservedShadowError."""
    plan = LoomPlan(
        loom_root=tmp_path,
        tasks=[
            Task(id="seed", kind="tool"),
            Task(
                id="ask",
                kind="agent",
                depends_on_all=["seed"],
                input_mapping={"__loom": "${task:seed:x}"},
            ),
        ],
    )
    with pytest.raises(ReservedShadowError) as exc:
        validate_mapping(plan)
    assert exc.value.field == "__loom"
    assert "io.md" in exc.value.doc


def test_reserved_shadow_static_via_lifecycle(tmp_path: Path):
    """Integration path: ``$LOOM validate`` / ``loom.init`` catches the
    same shadow through ``_static_validate``."""
    from loom import init
    from loom.naming import pascal_case_task_name

    root = tmp_path / "loom"
    root.mkdir()
    seed = root / "seed"
    seed.mkdir()
    (seed / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"x": {"type": "integer"}},
            "required": ["x"],
        },
    }))
    pascal = pascal_case_task_name("seed")
    (seed / "io_types.py").write_text(
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "@dataclass\n"
        f"class {pascal}Input:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
        "\n"
        "\n"
        "@dataclass\n"
        f"class {pascal}Output:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    x: int\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(x=d['x'])\n"
        "    def to_dict(self): return {'x': self.x}\n"
    )
    (seed / "tool.py").write_text(
        "from io_types import SeedInput, SeedOutput\n"
        "def seed(inp): return SeedOutput(x=1)\n"
    )

    ask = root / "ask"
    ask.mkdir()
    (ask / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    }))
    (ask / "prompt.md.j2").write_text("hello\n")

    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "ask", "kind": "agent", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"__loom": "${task:seed:x}"}},
        ],
    }))
    with pytest.raises(ReservedShadowError):
        init(tmp_path / "run", loom_root=root)

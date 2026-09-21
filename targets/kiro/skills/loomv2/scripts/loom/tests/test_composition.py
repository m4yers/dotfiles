"""Subgraph inlining, contracts, addressing model."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.engine.inline import expand_subgraphs
from loom.engine.models import LoomPlan, SubgraphSpec, Task
from loom.errors import NamespaceCollisionError


def _minimal_child(tmp_path: Path) -> Path:
    root = tmp_path / "child" / "loom"
    (root / "lint").mkdir(parents=True)
    (root / "lint" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {"type": "object", "additionalProperties": False},
    }))
    (root / "lint" / "tool.py").write_text(
        "from io_types import LintInput, LintOutput\n"
        "\n"
        "def lint(inp: LintInput) -> LintOutput:\n"
        "    return LintOutput()\n"
    )
    (root / "lint" / "io_types.py").write_text(
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class LintInput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class LintOutput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "lint", "kind": "tool", "version": 1}],
    }))
    return root


def test_inline_prefixes_addresses(tmp_path):
    child_root = _minimal_child(tmp_path)
    plan = LoomPlan(loom_root=tmp_path, tasks=[
        Task(id="root", kind="tool"),
        SubgraphSpec(id="c1", root_path=child_root, depends_on_all=["root"]),
    ])
    composed = expand_subgraphs(plan)
    ids = [t.id for t in composed.tasks if isinstance(t, Task)]
    assert "c1/lint" in ids


def test_sibling_collision(tmp_path):
    child_root = _minimal_child(tmp_path)
    plan = LoomPlan(loom_root=tmp_path, tasks=[
        SubgraphSpec(id="c1", root_path=child_root),
        SubgraphSpec(id="c1", root_path=child_root),
    ])
    with pytest.raises(NamespaceCollisionError):
        expand_subgraphs(plan)


def test_reuse_under_distinct_ids(tmp_path):
    child_root = _minimal_child(tmp_path)
    plan = LoomPlan(loom_root=tmp_path, tasks=[
        SubgraphSpec(id="review-code", root_path=child_root),
        SubgraphSpec(id="review-docs", root_path=child_root),
    ])
    composed = expand_subgraphs(plan)
    ids = {t.id for t in composed.tasks if isinstance(t, Task)}
    assert "review-code/lint" in ids
    assert "review-docs/lint" in ids


def test_inlined_metadata(tmp_path):
    child_root = _minimal_child(tmp_path)
    plan = LoomPlan(loom_root=tmp_path, tasks=[
        SubgraphSpec(id="c1", root_path=child_root),
    ])
    composed = expand_subgraphs(plan)
    inlined = [t for t in composed.tasks if isinstance(t, Task) and t.inlined_from_subgraph]
    assert inlined
    for t in inlined:
        assert t.instance_uid
        assert t.source_root == child_root


def test_latch_exit_child_embeds(tmp_path):
    """Regression: a child graph whose exit task is a loop latch must
    still resolve a single entry/exit and inline cleanly."""
    root = _minimal_child(tmp_path)
    # Turn the child's sole task into a self-latch (it stays the exit:
    # back-edges live in the latch declaration, not the dep edge set).
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "lint", "kind": "tool", "version": 1}],
        "latches": [{"task": "lint", "header": "lint", "fuel": 2}],
    }))
    plan = LoomPlan(loom_root=tmp_path, tasks=[
        Task(id="root", kind="tool"),
        SubgraphSpec(id="c1", root_path=root, depends_on_all=["root"]),
    ])
    composed = expand_subgraphs(plan)
    ids = {t.id for t in composed.tasks if isinstance(t, Task)}
    assert "c1/lint" in ids
    lint = next(t for t in composed.tasks if isinstance(t, Task) and t.id == "c1/lint")
    assert lint.latch is not None and lint.latch.fuel == 2



# ---- ref-instancing composition invariants -----------------------


def _write_agent_task(root: Path, name: str) -> None:
    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
    }))
    (folder / "prompt.md.j2").write_text("Q: {{ input.q }}\n")


def _write_tool_task(root: Path, name: str) -> None:
    from loom.naming import pascal_case_task_name

    folder = root / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
    }))
    pascal = pascal_case_task_name(name)
    (folder / "io_types.py").write_text(
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n\n"
        f"@dataclass\nclass {pascal}Input:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    q: str\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(q=d['q'])\n"
        "    def to_dict(self): return {'q': self.q}\n"
        "\n\n"
        f"@dataclass\nclass {pascal}Output:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    a: str\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(a=d['a'])\n"
        "    def to_dict(self): return {'a': self.a}\n"
    )
    snake = name.replace("-", "_")
    (folder / "tool.py").write_text(
        f"from io_types import {pascal}Input, {pascal}Output\n"
        "\n"
        f"def {snake}(inp: {pascal}Input) -> {pascal}Output:\n"
        f"    return {pascal}Output(a=inp.q)\n"
    )


def test_composition_accepts_two_instances_sharing_ref(tmp_path):
    """Two distinct-id entries sharing the same `ref` pass composition
    cleanly — shared folder → distinct instances."""
    from loom.plan import from_graph_yaml
    from loom.validate.composition import validate_composition

    root = tmp_path / "loom"
    _write_tool_task(root, "seed")
    _write_agent_task(root, "research")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "research-q1", "kind": "agent", "version": 1,
             "ref": "research", "depends_on_all": ["seed"],
             "input": {"q": "${task:seed:a}"}},
            {"id": "research-q2", "kind": "agent", "version": 1,
             "ref": "research", "depends_on_all": ["seed"],
             "input": {"q": "${task:seed:a}"}},
        ],
    }))
    plan = from_graph_yaml(root)
    # Both ref-instanced tasks carry a `folder` decoupled from `id`.
    from loom.engine.models import Task

    instances = [
        t for t in plan.tasks
        if isinstance(t, Task) and t.id.startswith("research-q")
    ]
    assert len(instances) == 2
    for t in instances:
        assert t.folder == root / "research"
    # Composition passes.
    validate_composition(plan)


def test_composition_rejects_kind_mismatch_on_shared_folder(tmp_path):
    """A ref-shared folder whose detected kind differs from the entry's
    declared kind trips :class:`TaskRefError`."""
    from loom.plan import from_graph_yaml
    from loom.validate.composition import validate_composition
    from loom.errors import TaskRefError

    root = tmp_path / "loom"
    _write_tool_task(root, "seed")
    _write_tool_task(root, "shared")  # tool folder
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            # Declared kind is `agent`, but the shared folder has
            # `tool.py` — mismatch.
            {"id": "one", "kind": "agent", "version": 1,
             "ref": "shared", "depends_on_all": ["seed"],
             "input": {"q": "${task:seed:a}"}},
        ],
    }))
    plan = from_graph_yaml(root)
    with pytest.raises(TaskRefError, match="detected kind"):
        validate_composition(plan)

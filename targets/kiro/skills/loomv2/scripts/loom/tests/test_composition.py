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
        "input": {"type": "object"},
        "output": {"type": "object"},
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

"""io.yaml version-pin enforcement at load time."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.discovery import load_io_yaml
from loom.errors import TaskVersionMismatchError
from loom.engine.inline import expand_subgraphs
from loom.engine.models import Task
from loom.plan import from_graph_yaml
from loom.validate.versions import check_versions
from tests.conftest import bump_io_version


def test_root_drift(tool_task_folder: Path):
    plan = from_graph_yaml(tool_task_folder)
    bump_io_version(tool_task_folder / "compute", 2)
    with pytest.raises(TaskVersionMismatchError) as exc:
        check_versions(plan, tool_task_folder / "graph.yaml")
    assert exc.value.pinned_version == 1
    assert exc.value.current_version == 2
    assert exc.value.canonical_address == "compute"


def test_round_trip_clean(tool_task_folder: Path):
    plan = from_graph_yaml(tool_task_folder)
    check_versions(plan, tool_task_folder / "graph.yaml")


def test_missing_version_meta_schema(tmp_path):
    task = tmp_path / "compute"
    task.mkdir()
    (task / "io.yaml").write_text(yaml.safe_dump({
        "input": {"type": "object", "additionalProperties": False},
        "output": {"type": "object", "additionalProperties": False},
    }))
    from loom.errors import IOYamlError

    with pytest.raises(IOYamlError):
        load_io_yaml(task)


def test_error_carries_graph_path(tool_task_folder: Path):
    plan = from_graph_yaml(tool_task_folder)
    bump_io_version(tool_task_folder / "compute", 3)
    with pytest.raises(TaskVersionMismatchError) as exc:
        check_versions(plan, tool_task_folder / "graph.yaml")
    assert exc.value.graph_yaml == tool_task_folder / "graph.yaml"


def test_inlined_subgraph_task_resolved_via_source_root(hello_graph: Path):
    """Regression: check_versions must resolve inlined subgraph task
    folders against ``task.source_root`` — otherwise it looks for
    ``<parent_loom>/lint-text`` (which does not exist) and raises
    TaskFolderError instead of running the version check."""
    parent_loom = hello_graph / "loom"
    plan = from_graph_yaml(parent_loom)
    composed = expand_subgraphs(plan)
    # Sanity: at least one inlined child task with source_root set.
    inlined = [
        t for t in composed.tasks
        if isinstance(t, Task) and t.source_root is not None
    ]
    assert inlined, "expected inlined subgraph tasks in composed plan"
    # Must NOT raise TaskFolderError; folders live under child loom root.
    check_versions(composed, parent_loom / "graph.yaml")


def test_inlined_subgraph_version_drift(hello_graph: Path):
    """When a subgraph child io.yaml drifts, the drift is reported
    against the inlined canonical address (namespace-prefixed)."""
    parent_loom = hello_graph / "loom"
    child_task_folder = hello_graph / "child" / "loom" / "lint-text"
    plan = from_graph_yaml(parent_loom)
    composed = expand_subgraphs(plan)
    bump_io_version(child_task_folder, 2)
    with pytest.raises(TaskVersionMismatchError) as exc:
        check_versions(composed, parent_loom / "graph.yaml")
    # The bumped io.yaml is the child's; the canonical address is the
    # inlined namespace-prefixed form (child-lint/lint-text or
    # child-relint/lint-text — either is a valid first-detected drift).
    assert exc.value.canonical_address.endswith("/lint-text")
    assert exc.value.current_version == 2



# ---- ref-instanced version pin --------------------------------------


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


def _write_tool_seed(root: Path) -> None:
    from loom.naming import pascal_case_task_name

    folder = root / "seed"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
    }))
    pascal = pascal_case_task_name("seed")
    (folder / "io_types.py").write_text(
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n\n"
        f"@dataclass\nclass {pascal}Input:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
        "\n\n"
        f"@dataclass\nclass {pascal}Output:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    a: str\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(a=d['a'])\n"
        "    def to_dict(self): return {'a': self.a}\n"
    )
    (folder / "tool.py").write_text(
        f"from io_types import {pascal}Input, {pascal}Output\n"
        "\n"
        f"def seed(inp: {pascal}Input) -> {pascal}Output:\n"
        f"    return {pascal}Output(a='seed')\n"
    )


def _ref_instanced_loom(tmp_path: Path) -> Path:
    """Build a fan-out loom with three ref-instanced agent tasks."""
    root = tmp_path / "loom"
    _write_tool_seed(root)
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
    return root


def test_ref_instances_pin_shared_version(tmp_path: Path):
    """Each ref-instanced entry pins the SHARED io.yaml version."""
    root = _ref_instanced_loom(tmp_path)
    plan = from_graph_yaml(root)
    # Both ref instances have pinned_version=1 (from graph.yaml) and
    # folder pointing at the shared `research/` directory.
    instances = [
        t for t in plan.tasks
        if isinstance(t, Task) and t.id.startswith("research-q")
    ]
    assert len(instances) == 2
    for t in instances:
        assert t.pinned_version == 1
        assert t.folder == root / "research"
    # Round-trip clean: shared v1 == pinned v1.
    check_versions(plan, root / "graph.yaml")


def test_ref_instance_shared_drift_trips_each_instance(tmp_path: Path):
    """Bumping the SHARED folder's io.yaml version trips
    ``TaskVersionMismatchError`` on the first ref instance encountered.
    Each instance would trip independently if the earlier ones didn't
    already halt the check."""
    root = _ref_instanced_loom(tmp_path)
    plan = from_graph_yaml(root)
    bump_io_version(root / "research", 2)
    with pytest.raises(TaskVersionMismatchError) as exc:
        check_versions(plan, root / "graph.yaml")
    assert exc.value.canonical_address.startswith("research-q")
    assert exc.value.pinned_version == 1
    assert exc.value.current_version == 2


def test_graph_new_repins_all_ref_instances(tmp_path: Path):
    """`$LOOM graph new` restamp mode re-pins every ref-instanced
    entry against the SHARED folder's current version."""
    from loom.scaffold.graph import new_graph
    import yaml as _yaml

    root = _ref_instanced_loom(tmp_path)
    bump_io_version(root / "research", 3)
    new_graph(root)
    parsed = _yaml.safe_load((root / "graph.yaml").read_text())
    for entry in parsed["tasks"]:
        if entry["id"].startswith("research-q"):
            assert entry["version"] == 3
            assert entry["ref"] == "research"

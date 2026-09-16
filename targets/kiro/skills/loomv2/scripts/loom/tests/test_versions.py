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
        "input": {"type": "object"},
        "output": {"type": "object"},
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

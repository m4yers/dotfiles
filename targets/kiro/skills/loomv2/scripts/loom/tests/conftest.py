"""Shared pytest fixtures for loom v2 tests.

Includes temp workdirs, sample per-kind loom trees, canonical
single-entry/exit builders, matched pair builders (standalone child +
parent embedding via subgraph), and a version-bump helper used by
test_versions.py.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_workdir(tmp_path: Path) -> Path:
    """Fresh empty workdir under pytest's tmp_path."""
    return tmp_path / "workdir"


@pytest.fixture
def hello_graph(tmp_path: Path) -> Path:
    """Copy references/hello-graph AND the schemas/ folder into a scratch
    dir so ``$ref`` paths in the example task io.yaml files (which climb
    four levels up to ``schemas/``) resolve correctly."""
    src_skill = Path(__file__).parents[3]
    dst_skill = tmp_path / "skill"
    shutil.copytree(
        src_skill / "references" / "hello-graph",
        dst_skill / "references" / "hello-graph",
    )
    shutil.copytree(src_skill / "schemas", dst_skill / "schemas")
    return dst_skill / "references" / "hello-graph"


@pytest.fixture
def tool_task_folder(tmp_path: Path) -> Path:
    """Minimal single-tool-task loom root."""
    root = tmp_path / "loom"
    task = root / "compute"
    task.mkdir(parents=True)
    (task / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"m": {"type": "integer"}},
            "required": ["m"],
        },
    }))
    (task / "tool.py").write_text(
        "def compute(inp):\n    return {'m': inp['n'] * 2}\n"
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "compute", "kind": "tool", "version": 1}],
    }))
    return root


def bump_io_version(task_folder: Path, new_version: int) -> None:
    """Rewrite ``<task_folder>/io.yaml`` with ``version = new_version``."""
    doc = yaml.safe_load((task_folder / "io.yaml").read_text())
    doc["version"] = new_version
    (task_folder / "io.yaml").write_text(yaml.safe_dump(doc))

"""Gap 4: runtime control — fail, reset (region-aware), is_done, is_stuck, status_summary."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


def _tool_only_root(tmp_path: Path) -> Path:
    """Two-tool loom: seed → compute."""
    from loom.naming import pascal_case_task_name

    root = tmp_path / "loom"
    root.mkdir()

    def add(name: str, out_val: int) -> None:
        d = root / name
        d.mkdir()
        (d / "io.yaml").write_text(yaml.safe_dump({
            "version": 1,
            "input": {"type": "object"},
            "output": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"n": {"type": "integer"}},
                "required": ["n"],
            },
        }))
        pascal = pascal_case_task_name(name)
        (d / "io_types.py").write_text(
            "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
            "from dataclasses import dataclass\n"
            "from typing import ClassVar\n"
            "\n"
            "@dataclass\n"
            f"class {pascal}Input:\n"
            "    VERSION: ClassVar[int] = 1\n"
            "    @classmethod\n"
            "    def from_dict(cls, d): return cls()\n"
            "    def to_dict(self): return {}\n"
            "\n"
            "@dataclass\n"
            f"class {pascal}Output:\n"
            "    VERSION: ClassVar[int] = 1\n"
            "    n: int\n"
            "    @classmethod\n"
            "    def from_dict(cls, d): return cls(n=d['n'])\n"
            "    def to_dict(self): return {'n': self.n}\n"
        )
        (d / "tool.py").write_text(
            f"from io_types import {pascal}Input, {pascal}Output\n"
            f"def {name}(inp: {pascal}Input) -> {pascal}Output:\n"
            f"    return {pascal}Output(n={out_val})\n"
        )

    add("seed", 3)
    add("compute", 9)
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "compute", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"]},
        ],
    }))
    return root


# ---- fail writes error.yaml ----

def test_fail_writes_error_yaml(tmp_path: Path):
    from loom import init
    from loom._lifecycle import resume as _resume
    from loom.engine.store import task_folder

    root = _tool_only_root(tmp_path)
    workdir = tmp_path / "run"
    init(workdir, loom_root=root)

    runtime = _resume(workdir)
    runtime.fail("compute", "human intervention")

    runtime = _resume(workdir)
    compute = next(t for t in runtime.plan.tasks if t.id == "compute")
    assert compute.status == "failed"
    err = yaml.safe_load(
        (task_folder(workdir, runtime.plan, "compute") / "error.yaml").read_text()
    )
    assert err["message"] == "human intervention"


# ---- reset on plain task ----

def test_reset_plain_task_clears_artifacts_and_preserves_seeded_input(tmp_path: Path):
    from loom import init
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.store import task_folder

    root = _tool_only_root(tmp_path)
    workdir = tmp_path / "run"
    init(workdir, loom_root=root)
    assert main(["runtime", "next", str(workdir)]) == 0

    runtime = _resume(workdir)
    seed_folder = task_folder(workdir, runtime.plan, "seed")
    assert (seed_folder / "output.yaml").exists()

    # Caller-seeded input.yaml on the entry (no `input:` mapping).
    (seed_folder / "input.yaml").write_text("{}\n")

    runtime.reset("seed")

    runtime = _resume(workdir)
    seed = next(t for t in runtime.plan.tasks if t.id == "seed")
    assert seed.status == "pending"
    assert not (seed_folder / "output.yaml").exists()
    assert (seed_folder / "input.yaml").exists()  # preserved


# ---- reset on loop body: region-aware, fuel not restored ----

def test_reset_loop_body_region_aware_fuel_preserved(tmp_path: Path):
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.store import completed_iter_indices, task_folder

    from loom.naming import pascal_case_task_name

    root = tmp_path / "loom"
    root.mkdir()

    def add(name: str) -> None:
        d = root / name
        d.mkdir()
        (d / "io.yaml").write_text(yaml.safe_dump({
            "version": 1,
            "input": {"type": "object"},
            "output": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"n": {"type": "integer"}},
                "required": ["n"],
            },
        }))
        pascal = pascal_case_task_name(name)
        (d / "io_types.py").write_text(
            "from dataclasses import dataclass\n"
            "from typing import ClassVar\n"
            "\n"
            "@dataclass\n"
            f"class {pascal}Input:\n"
            "    VERSION: ClassVar[int] = 1\n"
            "    @classmethod\n"
            "    def from_dict(cls, d): return cls()\n"
            "    def to_dict(self): return {}\n"
            "\n"
            "@dataclass\n"
            f"class {pascal}Output:\n"
            "    VERSION: ClassVar[int] = 1\n"
            "    n: int\n"
            "    @classmethod\n"
            "    def from_dict(cls, d): return cls(n=d['n'])\n"
            "    def to_dict(self): return {'n': self.n}\n"
        )
        (d / "tool.py").write_text(
            f"from io_types import {pascal}Input, {pascal}Output\n"
            f"def {name}(inp: {pascal}Input) -> {pascal}Output:\n"
            f"    return {pascal}Output(n=1)\n"
        )

    add("boot")
    add("grind")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "boot", "kind": "tool", "version": 1},
            {"id": "grind", "kind": "tool", "version": 1,
             "depends_on_all": ["boot"]},
        ],
        "latches": [
            {"task": "grind", "header": "grind", "fuel": 3},
        ],
    }))
    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    assert main(["runtime", "next", str(workdir)]) == 0

    runtime = _resume(workdir)
    grind_folder = task_folder(workdir, runtime.plan, "grind")
    assert completed_iter_indices(grind_folder) == [0, 1, 2]
    grind = next(t for t in runtime.plan.tasks if t.id == "grind")
    assert grind.latch.fuel == 0

    runtime.reset("grind")

    runtime = _resume(workdir)
    grind_folder = task_folder(workdir, runtime.plan, "grind")
    grind = next(t for t in runtime.plan.tasks if t.id == "grind")
    assert grind.status == "pending"
    assert completed_iter_indices(grind_folder) == []
    # Fuel is NOT restored — it reflects rounds already consumed.
    assert grind.latch.fuel == 0


# ---- is_done / is_stuck / status_summary shape ----

def test_status_helpers_shape(tmp_path: Path):
    from loom import init
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume

    root = _tool_only_root(tmp_path)
    workdir = tmp_path / "run"
    init(workdir, loom_root=root)

    runtime = _resume(workdir)
    summary = runtime.status_summary()
    assert set(summary) == {"total", "is_done", "is_stuck", "counts"}
    assert summary["total"] == 2
    assert summary["is_done"] is False
    assert summary["is_stuck"] is False
    assert set(summary["counts"]) == {
        "pending", "ready", "running", "done", "failed", "skipped"
    }
    assert summary["counts"]["pending"] == 2

    assert main(["runtime", "next", str(workdir)]) == 0
    runtime = _resume(workdir)
    assert runtime.is_done() is True
    assert runtime.is_stuck() is False
    summary = runtime.status_summary()
    assert summary["is_done"] is True
    assert summary["counts"]["done"] == 2

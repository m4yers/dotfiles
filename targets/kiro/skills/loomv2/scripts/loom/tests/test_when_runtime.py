"""Gap 1: runtime ``when`` predicate evaluation at dispatch.

  - Clean false → task is skipped and ``skip-reason.yaml`` (with
    ``reason_kind: when-false``) is written.
  - Cascade-skip → downstream tasks get ``skip-reason.yaml`` with
    ``reason_kind: cascade-skip``.
  - Predicate that fails to evaluate raises PredicateEvalError — halts
    the run loudly instead of coercing to falsy.
"""
from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
import yaml


_SKIP_REASON_META = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "schemas" / "skip-reason.yaml").read_text()
)


def _validate_skip_reason(doc: dict) -> None:
    jsonschema.validate(doc, _SKIP_REASON_META)


def _write_seed_tool(root: Path, name: str, pascal: str, output_doc: dict) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    fields = list(output_doc.keys())
    (d / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object"},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {k: {"type": "string" if isinstance(v, str) else "integer"}
                           for k, v in output_doc.items()},
            "required": fields,
        },
    }))
    body = "\n".join(
        [f"    {k}: {'str' if isinstance(v, str) else 'int'}" for k, v in output_doc.items()]
    )
    kwargs = ", ".join(f"{k}={v!r}" for k, v in output_doc.items())
    (d / "io_types.py").write_text(
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
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
        f"{body}\n"
        "    @classmethod\n"
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {fields!r}}})\n"
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {fields!r}}}\n"
    )
    (d / "tool.py").write_text(
        f"from io_types import {pascal}Input, {pascal}Output\n"
        "\n"
        f"def {name.replace('-', '_')}(inp: {pascal}Input) -> {pascal}Output:\n"
        f"    return {pascal}Output({kwargs})\n"
    )


def _write_agent(root: Path, name: str) -> None:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object"},
        "output": {"type": "object"},
    }))
    (d / "prompt.md.j2").write_text("say something\n")


# ---- clean-false when → skip + skip-reason.yaml (when-false) ----

def test_when_false_skips_task_and_writes_reason(tmp_path: Path):
    from loom import init
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.store import task_folder

    root = tmp_path / "loom"
    root.mkdir()
    _write_seed_tool(root, "gate", "Gate", {"go": "no"})
    _write_agent(root, "downstream")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "gate", "kind": "tool", "version": 1},
            {"id": "downstream", "kind": "agent", "version": 1,
             "depends_on_all": ["gate"],
             "when": "${task:gate:go == 'yes'}"},
        ],
    }))
    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    assert main(["runtime", "next", str(workdir)]) == 0

    runtime = _resume(workdir)
    downstream = next(t for t in runtime.plan.tasks if t.id == "downstream")
    assert downstream.status == "skipped"
    doc = yaml.safe_load(
        (task_folder(workdir, runtime.plan, "downstream") / "skip-reason.yaml").read_text()
    )
    assert doc["task_id"] == "downstream"
    assert doc["reason_kind"] == "when-false"
    assert doc["predicate"] == "${task:gate:go == 'yes'}"
    _validate_skip_reason(doc)


# ---- cascade-skip cascade → skip-reason.yaml (cascade-skip) ----

def test_cascade_skip_writes_reason(tmp_path: Path):
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.store import task_folder

    root = tmp_path / "loom"
    root.mkdir()
    _write_seed_tool(root, "gate", "Gate", {"go": "no"})
    _write_agent(root, "middle")
    _write_agent(root, "tail")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "gate", "kind": "tool", "version": 1},
            {"id": "middle", "kind": "agent", "version": 1,
             "depends_on_all": ["gate"],
             "when": "${task:gate:go == 'yes'}"},
            {"id": "tail", "kind": "agent", "version": 1,
             "depends_on_all": ["middle"]},
        ],
    }))
    workdir = tmp_path / "run"
    main(["runtime", "init", str(workdir), "--loom-root", str(root)])
    # First next: gate runs, middle skips (when-false).
    main(["runtime", "next", str(workdir)])
    # Second next: tail cascade-skips because middle is skipped.
    main(["runtime", "next", str(workdir)])

    runtime = _resume(workdir)
    tail = next(t for t in runtime.plan.tasks if t.id == "tail")
    assert tail.status == "skipped"
    doc = yaml.safe_load(
        (task_folder(workdir, runtime.plan, "tail") / "skip-reason.yaml").read_text()
    )
    assert doc["task_id"] == "tail"
    assert doc["reason_kind"] == "cascade-skip"
    assert "predicate" not in doc
    _validate_skip_reason(doc)


# ---- predicate eval error → PredicateEvalError abort ----

def test_predicate_eval_error_aborts_run(tmp_path: Path):
    from loom.__main__ import main
    from loom.errors import PredicateEvalError

    root = tmp_path / "loom"
    root.mkdir()
    _write_seed_tool(root, "gate", "Gate", {"go": "yes"})
    _write_agent(root, "downstream")
    # Deliberately broken JMESPath: `][` is a parse error.
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "gate", "kind": "tool", "version": 1},
            {"id": "downstream", "kind": "agent", "version": 1,
             "depends_on_all": ["gate"],
             "when": "${task:gate:][invalid}"},
        ],
    }))
    workdir = tmp_path / "run"
    main(["runtime", "init", str(workdir), "--loom-root", str(root)])
    with pytest.raises(PredicateEvalError):
        main(["runtime", "next", str(workdir)])

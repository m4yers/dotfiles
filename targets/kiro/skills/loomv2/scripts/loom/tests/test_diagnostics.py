"""Gap 6: engine-written diagnostic YAML files.

  - ``stderr.yaml`` on stderr output and on failure.
  - ``schema-error.yaml`` for both input and output phases.
  - ``skip-reason.yaml`` on skip.
Each doc validates against its schema.
"""
from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
import yaml


_SCHEMAS_ROOT = Path(__file__).resolve().parents[3] / "schemas"
_STDERR_META = yaml.safe_load((_SCHEMAS_ROOT / "stderr.yaml").read_text())
_SCHEMA_ERROR_META = yaml.safe_load((_SCHEMAS_ROOT / "schema-error.yaml").read_text())
_SKIP_REASON_META = yaml.safe_load((_SCHEMAS_ROOT / "skip-reason.yaml").read_text())


def _val(doc, meta):
    jsonschema.validate(doc, meta)


# ---- stderr.yaml on non-empty stderr ----

def _make_folder_with_stderr(tmp_path: Path, body: str) -> Path:
    folder = tmp_path / "task"
    folder.mkdir()
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    }))
    (folder / "io_types.py").write_text(
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "@dataclass\n"
        "class NoisyInput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
        "\n"
        "@dataclass\n"
        "class NoisyOutput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    n: int\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(n=d['n'])\n"
        "    def to_dict(self): return {'n': self.n}\n"
    )
    (folder / "tool.py").write_text(body)
    (folder / "input.yaml").write_text("{}\n")
    return folder


def test_stderr_yaml_on_non_empty_stderr(tmp_path: Path):
    from loom.engine.models import Task
    from loom.engine.tool_dispatch import dispatch_tool

    folder = _make_folder_with_stderr(
        tmp_path,
        "import sys\n"
        "from io_types import NoisyInput, NoisyOutput\n"
        "def noisy(inp: NoisyInput) -> NoisyOutput:\n"
        "    print('deprecation warning', file=sys.stderr)\n"
        "    return NoisyOutput(n=1)\n",
    )
    dispatch_tool(Task(id="noisy", kind="tool"), folder)
    doc = yaml.safe_load((folder / "stderr.yaml").read_text())
    assert doc["task_id"] == "noisy"
    assert doc["kind"] == "tool"
    assert "deprecation warning" in doc["text"]
    _val(doc, _STDERR_META)


def test_stderr_yaml_on_failure(tmp_path: Path):
    from loom.engine.models import Task
    from loom.engine.tool_dispatch import dispatch_tool
    from loom.errors import ToolTaskError

    folder = _make_folder_with_stderr(
        tmp_path,
        "from io_types import NoisyInput, NoisyOutput\n"
        "def noisy(inp: NoisyInput) -> NoisyOutput:\n"
        "    raise ValueError('boom')\n",
    )
    with pytest.raises(ToolTaskError):
        dispatch_tool(Task(id="noisy", kind="tool"), folder)
    # stderr.yaml exists even when captured stderr is empty (failure).
    doc = yaml.safe_load((folder / "stderr.yaml").read_text())
    _val(doc, _STDERR_META)


def test_stderr_yaml_absent_when_clean(tmp_path: Path):
    from loom.engine.models import Task
    from loom.engine.tool_dispatch import dispatch_tool

    folder = _make_folder_with_stderr(
        tmp_path,
        "from io_types import NoisyInput, NoisyOutput\n"
        "def noisy(inp: NoisyInput) -> NoisyOutput:\n"
        "    return NoisyOutput(n=1)\n",
    )
    dispatch_tool(Task(id="noisy", kind="tool"), folder)
    assert not (folder / "stderr.yaml").exists()


# ---- schema-error.yaml: output phase ----

def test_schema_error_on_output_validation(tmp_path: Path):
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.store import task_folder
    from loom.errors import OutputSchemaError

    root = tmp_path / "loom"
    root.mkdir()
    task = root / "ask"
    task.mkdir()
    (task / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    }))
    (task / "prompt.md.j2").write_text("hi {{ input }}\n")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "ask", "kind": "agent", "version": 1}],
    }))
    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    main(["runtime", "next", str(workdir)])
    # Write an output missing the required 'answer'.
    (workdir / "tasks" / "01-ask" / "output.yaml").write_text("{}\n")
    with pytest.raises(OutputSchemaError):
        main(["runtime", "complete", str(workdir), "ask"])

    runtime = _resume(workdir)
    folder = task_folder(workdir, runtime.plan, "ask")
    doc = yaml.safe_load((folder / "schema-error.yaml").read_text())
    assert doc["phase"] == "output"
    assert doc["task_id"] == "ask"
    _val(doc, _SCHEMA_ERROR_META)


# ---- schema-error.yaml: input phase (covered end-to-end by mapping test) ----

def test_schema_error_input_phase_validates(tmp_path: Path):
    """Sanity: an input-phase schema-error.yaml validates against its schema."""
    from loom.engine.store import write_schema_error_yaml

    folder = tmp_path / "task"
    folder.mkdir()
    write_schema_error_yaml(folder, "target", "input", "'n' is a required property")
    doc = yaml.safe_load((folder / "schema-error.yaml").read_text())
    _val(doc, _SCHEMA_ERROR_META)
    assert doc["phase"] == "input"


# ---- skip-reason.yaml written on skip ----

def test_skip_reason_yaml_validates(tmp_path: Path):
    from loom.engine.store import write_skip_reason_yaml

    folder = tmp_path / "task"
    folder.mkdir()
    write_skip_reason_yaml(folder, "downstream", "cascade-skip")
    doc = yaml.safe_load((folder / "skip-reason.yaml").read_text())
    _val(doc, _SKIP_REASON_META)
    assert doc["reason_kind"] == "cascade-skip"
    assert "predicate" not in doc

    write_skip_reason_yaml(folder, "downstream", "when-false", predicate="${task:x:y}")
    doc = yaml.safe_load((folder / "skip-reason.yaml").read_text())
    _val(doc, _SKIP_REASON_META)
    assert doc["reason_kind"] == "when-false"
    assert doc["predicate"] == "${task:x:y}"

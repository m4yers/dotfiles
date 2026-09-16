"""tool.py + io_types.py dispatch with typed IO."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from loom.engine.models import Task
from loom.engine.tool_dispatch import dispatch_tool
from loom.errors import ToolIOVersionMismatchError, ToolTaskError


_IO_YAML = yaml.safe_dump({
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
})


_IO_TYPES_PY_V1 = """\
# generated from io.yaml v1 by $LOOM task io-python — do not edit
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ComputeInput:
    VERSION: ClassVar[int] = 1
    n: int

    @classmethod
    def from_dict(cls, d):
        return cls(n=d["n"])

    def to_dict(self):
        return {"n": self.n}


@dataclass
class ComputeOutput:
    VERSION: ClassVar[int] = 1
    m: int

    @classmethod
    def from_dict(cls, d):
        return cls(m=d["m"])

    def to_dict(self):
        return {"m": self.m}
"""


def _tool_py(body: str) -> str:
    return "from io_types import ComputeInput, ComputeOutput\n\n" + body


def _make_folder(
    tmp_path: Path,
    tool_body: str,
    *,
    write_io_types: bool = True,
    io_types_text: str = _IO_TYPES_PY_V1,
) -> Path:
    folder = tmp_path / "task"
    folder.mkdir()
    (folder / "io.yaml").write_text(_IO_YAML)
    if write_io_types:
        (folder / "io_types.py").write_text(io_types_text)
    (folder / "tool.py").write_text(_tool_py(tool_body))
    (folder / "input.yaml").write_text(yaml.safe_dump({"n": 3}))
    return folder


def test_positive(tmp_path):
    folder = _make_folder(
        tmp_path,
        "def compute(inp: ComputeInput) -> ComputeOutput:\n"
        "    return ComputeOutput(m=inp.n * 2)\n",
    )
    dispatch_tool(Task(id="compute", kind="tool"), folder)
    assert yaml.safe_load((folder / "output.yaml").read_text()) == {"m": 6}


def test_missing_io_types(tmp_path):
    """No io_types.py alongside tool.py → ToolTaskError → task io-python remedy."""
    folder = _make_folder(
        tmp_path,
        "def compute(inp): return None\n",
        write_io_types=False,
    )
    with pytest.raises(ToolTaskError) as exc:
        dispatch_tool(Task(id="compute", kind="tool"), folder)
    msg = str(exc.value)
    assert "io_types.py" in msg
    assert "$LOOM task io-python compute" in msg


def test_missing_generated_classes(tmp_path):
    """io_types.py present but empty → classes absent → helpful ToolTaskError."""
    folder = _make_folder(
        tmp_path,
        "def compute(inp): return None\n",
        io_types_text="# generated placeholder\n",
    )
    with pytest.raises(ToolTaskError) as exc:
        dispatch_tool(Task(id="compute", kind="tool"), folder)
    msg = str(exc.value)
    assert "ComputeInput" in msg and "ComputeOutput" in msg
    assert "$LOOM task io-python compute" in msg


def test_version_mismatch(tmp_path):
    """io_types.py at v1 while io.yaml bumped to v2 → dedicated error."""
    folder = _make_folder(
        tmp_path,
        "def compute(inp: ComputeInput) -> ComputeOutput:\n"
        "    return ComputeOutput(m=inp.n * 2)\n",
    )
    bumped = yaml.safe_load(_IO_YAML)
    bumped["version"] = 2
    (folder / "io.yaml").write_text(yaml.safe_dump(bumped))
    with pytest.raises(ToolIOVersionMismatchError) as exc:
        dispatch_tool(Task(id="compute", kind="tool"), folder)
    assert exc.value.class_version == 1
    assert exc.value.io_version == 2
    assert "$LOOM task io-python" in str(exc.value)


def test_missing_function(tmp_path):
    folder = _make_folder(
        tmp_path,
        "def wrong_name(inp): return ComputeOutput(m=0)\n",
    )
    with pytest.raises(ToolTaskError) as exc:
        dispatch_tool(Task(id="compute", kind="tool"), folder)
    assert "no function named 'compute'" in str(exc.value)


def test_raises_writes_error_yaml(tmp_path):
    folder = _make_folder(
        tmp_path,
        "def compute(inp: ComputeInput) -> ComputeOutput:\n"
        "    raise ValueError('boom')\n",
    )
    with pytest.raises(ToolTaskError):
        dispatch_tool(Task(id="compute", kind="tool"), folder)
    assert (folder / "error.yaml").exists()


def test_wrong_return_type(tmp_path):
    """fn returns a raw dict → ToolTaskError."""
    folder = _make_folder(
        tmp_path,
        "def compute(inp: ComputeInput):\n    return {'m': inp.n * 2}\n",
    )
    with pytest.raises(ToolTaskError) as exc:
        dispatch_tool(Task(id="compute", kind="tool"), folder)
    assert "ComputeOutput" in str(exc.value)


def test_namespaced_task_id(tmp_path):
    """Subgraph-inlined address 'sub/compute' still resolves classes."""
    folder = _make_folder(
        tmp_path,
        "def compute(inp: ComputeInput) -> ComputeOutput:\n"
        "    return ComputeOutput(m=inp.n + 1)\n",
    )
    dispatch_tool(Task(id="sub/compute", kind="tool"), folder)
    assert yaml.safe_load((folder / "output.yaml").read_text()) == {"m": 4}


def test_sys_modules_io_types_restored(tmp_path):
    """Pre-existing sys.modules['io_types'] is preserved across dispatch."""
    sentinel = type("Sentinel", (), {})()
    sys.modules["io_types"] = sentinel  # type: ignore[assignment]
    try:
        folder = _make_folder(
            tmp_path,
            "def compute(inp: ComputeInput) -> ComputeOutput:\n"
            "    return ComputeOutput(m=inp.n * 2)\n",
        )
        dispatch_tool(Task(id="compute", kind="tool"), folder)
        assert sys.modules["io_types"] is sentinel
    finally:
        sys.modules.pop("io_types", None)


def test_sys_modules_io_types_cleared_when_absent(tmp_path):
    """If no pre-existing sys.modules['io_types'], dispatch leaves it absent."""
    sys.modules.pop("io_types", None)
    folder = _make_folder(
        tmp_path,
        "def compute(inp: ComputeInput) -> ComputeOutput:\n"
        "    return ComputeOutput(m=inp.n * 2)\n",
    )
    dispatch_tool(Task(id="compute", kind="tool"), folder)
    assert "io_types" not in sys.modules

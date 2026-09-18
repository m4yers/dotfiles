"""Verify `$LOOM task new`, `$LOOM task io-python`, `$LOOM graph new`."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.errors import IOYamlError, TaskFolderError
from loom.scaffold import io_python, new_graph, new_task
from tests.conftest import bump_io_version


_TOOL_IO_YAML = yaml.safe_dump({
    "version": 1,
    "input": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"example": {"type": "string"}},
        "required": ["example"],
    },
    "output": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"result": {"type": "string"}},
        "required": ["result"],
    },
})


# ---- task new (folder only) ----

def test_task_new_creates_folder(tmp_path):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    folder = new_task(loom_root, "compute-thing")
    assert folder.is_dir()
    assert list(folder.iterdir()) == []  # folder only, no files


def test_task_new_bad_name(tmp_path):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    with pytest.raises(TaskFolderError):
        new_task(loom_root, "Bad Name")


def test_task_new_collision(tmp_path):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    new_task(loom_root, "compute")
    with pytest.raises(TaskFolderError) as exc:
        new_task(loom_root, "compute")
    assert "already exists" in str(exc.value)


# ---- task io-python (generate io_types.py) ----

def test_io_python_generates_types(tmp_path, capsys):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    folder = new_task(loom_root, "compute-thing")
    (folder / "io.yaml").write_text(_TOOL_IO_YAML)

    path = io_python(loom_root, "compute-thing")

    assert path == folder / "io_types.py"
    text = path.read_text()
    assert (
        text.startswith(
            "# generated from io.yaml v1 by $LOOM task io-python — do not edit"
        )
    )
    assert "class ComputeThingInput:" in text
    assert "class ComputeThingOutput:" in text
    assert "VERSION: ClassVar[int] = 1" in text
    assert "example: str" in text
    assert "result: str" in text
    assert "wrote io_types.py (v1)" in capsys.readouterr().out


def test_io_python_regeneration_overwrites(tmp_path, capsys):
    """Rewriting io.yaml and re-running overwrites the whole file with new v."""
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    folder = new_task(loom_root, "compute")
    (folder / "io.yaml").write_text(_TOOL_IO_YAML)
    io_python(loom_root, "compute")
    capsys.readouterr()

    # Stamp junk into the file to prove full overwrite.
    (folder / "io_types.py").write_text("garbage\n")
    bump_io_version(folder, 4)
    io_python(loom_root, "compute")

    text = (folder / "io_types.py").read_text()
    assert "garbage" not in text
    assert (
        "# generated from io.yaml v4 by $LOOM task io-python — do not edit"
        in text
    )
    assert "VERSION: ClassVar[int] = 4" in text
    assert "wrote io_types.py (v4)" in capsys.readouterr().out


def test_io_python_roundtrip_via_exec(tmp_path):
    """Sanity: generated io_types.py imports cleanly and round-trips."""
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    folder = new_task(loom_root, "compute-thing")
    (folder / "io.yaml").write_text(_TOOL_IO_YAML)
    io_python(loom_root, "compute-thing")

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_t", folder / "io_types.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    inp = mod.ComputeThingInput.from_dict({"example": "x"})
    assert inp.example == "x"
    assert inp.to_dict() == {"example": "x"}
    assert mod.ComputeThingInput.VERSION == 1
    assert mod.ComputeThingOutput.VERSION == 1


def test_io_python_missing_folder(tmp_path):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    with pytest.raises(TaskFolderError):
        io_python(loom_root, "nope")


def test_io_python_missing_io_yaml(tmp_path):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    new_task(loom_root, "compute")
    with pytest.raises(IOYamlError):
        io_python(loom_root, "compute")


def test_reserved_field_codegen_aliased_and_typed(tmp_path):
    """Codegen aliases ``__loom`` → ``loom`` (Python name-mangling
    workaround), imports ``LoomMeta`` / ``TaskMeta`` from
    ``loom.engine.reserved``, types the aliased field as ``LoomMeta``,
    and the round-trip goes through ``LoomMeta.from_dict`` /
    ``.to_dict``.
    """
    import importlib.util

    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    folder = new_task(loom_root, "some-task")
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "__loom": {},
                "other": {"type": "string"},
            },
            "required": ["__loom", "other"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        },
    }))

    io_python(loom_root, "some-task")

    text = (folder / "io_types.py").read_text()
    assert (
        "from loom.engine.reserved import LoomMeta, TaskMeta" in text
    )
    assert "loom: LoomMeta" in text

    spec = importlib.util.spec_from_file_location(
        "_reserved_alias_io_types", folder / "io_types.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    inp = mod.SomeTaskInput.from_dict(
        {"__loom": {"workdir": "/wd", "runtime": "/x/loom.sh"}, "other": "x"}
    )
    from loom.engine.reserved import LoomMeta

    assert isinstance(inp.loom, LoomMeta)
    assert inp.loom.workdir == "/wd"
    assert inp.other == "x"
    assert inp.to_dict() == {"__loom": {"workdir": "/wd", "runtime": "/x/loom.sh"}, "other": "x"}
    # Safe alias `loom`, not the mangled `_SomeTaskInput__loom`.
    assert "loom" in mod.SomeTaskInput.__annotations__
    assert "_SomeTaskInput__loom" not in mod.SomeTaskInput.__annotations__


# ---- graph new: scaffold (graph.yaml absent) ----

def _seed_tool(loom_root: Path, name: str) -> Path:
    folder = new_task(loom_root, name)
    (folder / "io.yaml").write_text(_TOOL_IO_YAML)
    (folder / "tool.py").write_text("# body\n")
    return folder


def test_graph_new_scaffolds_when_absent(tmp_path, capsys):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    _seed_tool(loom_root, "compute")
    new_graph(loom_root)
    doc = yaml.safe_load((loom_root / "graph.yaml").read_text())
    assert doc["tasks"][0] == {"id": "compute", "kind": "tool", "version": 1}
    assert "scaffolded" in capsys.readouterr().out


def test_graph_new_scaffolds_tool_sh_as_kind_tool(tmp_path, capsys):
    """A loom-root whose only task folder carries `tool.sh` (with
    io.yaml) scaffolds a `graph.yaml` entry with `kind: tool` and the
    io.yaml's pinned `version`."""
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    folder = new_task(loom_root, "banner-sh")
    (folder / "io.yaml").write_text(_TOOL_IO_YAML)
    (folder / "tool.sh").write_text("#!/usr/bin/env bash\nexit 0\n")
    (folder / "tool.sh").chmod(0o755)

    new_graph(loom_root)

    doc = yaml.safe_load((loom_root / "graph.yaml").read_text())
    assert doc["tasks"][0] == {
        "id": "banner-sh", "kind": "tool", "version": 1
    }
    assert "scaffolded" in capsys.readouterr().out


# ---- graph new: refresh (graph.yaml present) ----

def _write_authored_graph(loom_root: Path, text: str) -> Path:
    (loom_root / "graph.yaml").write_text(text)
    return loom_root / "graph.yaml"


def _seed_agent(loom_root: Path, name: str) -> Path:
    folder = new_task(loom_root, name)
    (folder / "io.yaml").write_text(_TOOL_IO_YAML)
    (folder / "prompt.md.j2").write_text("prompt\n")
    return folder


def test_graph_new_refresh_restamps_stale_pins(tmp_path, capsys):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    _seed_tool(loom_root, "compute")
    _seed_agent(loom_root, "review")
    authored = (
        "# Hand-authored graph.\n"
        "tasks:\n"
        "  - id: compute\n"
        "    kind: tool\n"
        "    version: 1\n"
        "  - {id: review, kind: agent, version: 1, depends_on_all: [compute],"
        " when: \"${task:compute:m > 0}\"}\n"
        "latches:\n"
        "  - {task: review, header: compute, fuel: 5}\n"
    )
    _write_authored_graph(loom_root, authored)
    bump_io_version(loom_root / "compute", 3)
    bump_io_version(loom_root / "review", 2)

    new_graph(loom_root)

    updated = (loom_root / "graph.yaml").read_text()
    expected = authored.replace(
        "    version: 1\n", "    version: 3\n"
    ).replace(
        "version: 1, depends_on_all", "version: 2, depends_on_all"
    )
    assert updated == expected
    assert "repinned 2 task(s)" in capsys.readouterr().out


def test_graph_new_refresh_up_to_date_reports_unchanged(tmp_path, capsys):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    _seed_tool(loom_root, "compute")
    authored = (
        "tasks:\n"
        "  - id: compute\n"
        "    kind: tool\n"
        "    version: 1\n"
    )
    _write_authored_graph(loom_root, authored)

    new_graph(loom_root)

    assert (loom_root / "graph.yaml").read_text() == authored
    assert "unchanged" in capsys.readouterr().out


def test_graph_new_refresh_preserves_subgraph_root(tmp_path, capsys):
    loom_root = tmp_path / "loom"
    loom_root.mkdir()
    _seed_tool(loom_root, "compute")
    authored = (
        "tasks:\n"
        "  - id: compute\n"
        "    kind: tool\n"
        "    version: 1\n"
        "  - id: child\n"
        "    kind: subgraph\n"
        "    version: 1\n"
        "    root: ../other/loom\n"
        "    depends_on_all: [compute]\n"
    )
    _write_authored_graph(loom_root, authored)
    bump_io_version(loom_root / "compute", 4)

    new_graph(loom_root)

    updated = (loom_root / "graph.yaml").read_text()
    # Subgraph version stays 1 (mirrors to_graph_yaml); compute bumped to 4.
    assert "    version: 4\n" in updated
    assert "root: ../other/loom" in updated
    assert "depends_on_all: [compute]" in updated
    assert "repinned 1 task(s)" in capsys.readouterr().out

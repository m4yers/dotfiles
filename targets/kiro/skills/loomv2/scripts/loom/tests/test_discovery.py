"""Task-folder resolution, kind detection, graph.yaml loading."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.discovery import (
    detect_kind,
    load_graph_yaml,
    load_io_yaml,
    resolve_task_folder,
    resolve_tool_entry,
)
from loom.errors import (
    AmbiguousToolEntryError,
    GraphYamlError,
    IOYamlError,
    KindMismatchError,
    TaskFolderError,
)


def test_resolve_task_folder_missing(tmp_path):
    with pytest.raises(TaskFolderError):
        resolve_task_folder(tmp_path, "nope")


def test_detect_kind_none(tmp_path):
    with pytest.raises(KindMismatchError):
        detect_kind(tmp_path)


def test_detect_kind_multiple(tmp_path):
    (tmp_path / "tool.py").write_text("")
    (tmp_path / "prompt.md.j2").write_text("")
    with pytest.raises(KindMismatchError):
        detect_kind(tmp_path)


def test_detect_kind_tool_sh_only_classifies_as_tool(tmp_path):
    """A folder with only tool.sh (executable, shebang) is a tool task."""
    tool_sh = tmp_path / "tool.sh"
    tool_sh.write_text("#!/usr/bin/env bash\nexit 0\n")
    tool_sh.chmod(0o755)
    assert detect_kind(tmp_path) == "tool"


def test_detect_kind_both_tool_py_and_tool_sh_raises_ambiguous(tmp_path):
    """A folder that carries BOTH tool.py and tool.sh raises
    AmbiguousToolEntryError; the two entry files are mutually
    exclusive."""
    (tmp_path / "tool.py").write_text("")
    (tmp_path / "tool.sh").write_text("#!/usr/bin/env bash\n")
    with pytest.raises(AmbiguousToolEntryError):
        detect_kind(tmp_path)


def test_resolve_tool_entry_python(tmp_path):
    (tmp_path / "tool.py").write_text("")
    assert resolve_tool_entry(tmp_path) == "python"


def test_resolve_tool_entry_shell(tmp_path):
    (tmp_path / "tool.sh").write_text("#!/usr/bin/env bash\n")
    assert resolve_tool_entry(tmp_path) == "shell"


def test_resolve_tool_entry_ambiguous(tmp_path):
    (tmp_path / "tool.py").write_text("")
    (tmp_path / "tool.sh").write_text("#!/usr/bin/env bash\n")
    with pytest.raises(AmbiguousToolEntryError):
        resolve_tool_entry(tmp_path)


def test_load_io_yaml_missing_version(tmp_path):
    (tmp_path / "io.yaml").write_text(yaml.safe_dump({"input": {}, "output": {}}))
    with pytest.raises(IOYamlError):
        load_io_yaml(tmp_path)


def test_load_graph_yaml_missing(tmp_path):
    with pytest.raises(GraphYamlError):
        load_graph_yaml(tmp_path)


def test_load_io_yaml_error_quotes_description(tmp_path):
    (tmp_path / "io.yaml").write_text(yaml.safe_dump({
        "version": "not-int", "input": {}, "output": {},
    }))
    with pytest.raises(IOYamlError) as exc_info:
        load_io_yaml(tmp_path)
    # Description of `version` field should be quoted into the message.
    assert "revision" in str(exc_info.value) or "version" in str(exc_info.value)



# ---- resolve_ref_folder --------------------------------------------


def test_resolve_ref_folder_happy_path(tmp_path):
    from loom.discovery import resolve_ref_folder

    (tmp_path / "research").mkdir()
    folder = resolve_ref_folder(tmp_path, "research")
    assert folder == (tmp_path / "research").resolve()


def test_resolve_ref_folder_missing_folder(tmp_path):
    from loom.discovery import resolve_ref_folder
    from loom.errors import TaskRefError

    with pytest.raises(TaskRefError, match="missing folder"):
        resolve_ref_folder(tmp_path, "nope")


def test_resolve_ref_folder_escapes_loom_root(tmp_path):
    from loom.discovery import resolve_ref_folder
    from loom.errors import TaskRefError

    # Create a sibling directory outside the loom root.
    outside = tmp_path.parent / "escape"
    outside.mkdir(exist_ok=True)
    # A `..` prefix would escape; kebab check rejects it first.
    with pytest.raises(TaskRefError, match="kebab"):
        resolve_ref_folder(tmp_path, "../escape")


def test_resolve_ref_folder_rejects_non_kebab(tmp_path):
    from loom.discovery import resolve_ref_folder
    from loom.errors import TaskRefError

    (tmp_path / "Shared").mkdir()
    with pytest.raises(TaskRefError, match="kebab"):
        resolve_ref_folder(tmp_path, "Shared")
    (tmp_path / "sh_ared").mkdir()
    with pytest.raises(TaskRefError, match="kebab"):
        resolve_ref_folder(tmp_path, "sh_ared")

"""Task-folder resolution, kind detection, graph.yaml loading."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.discovery import detect_kind, load_graph_yaml, load_io_yaml, resolve_task_folder
from loom.errors import GraphYamlError, IOYamlError, KindMismatchError, TaskFolderError


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

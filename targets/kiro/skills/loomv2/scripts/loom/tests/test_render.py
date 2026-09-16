"""Jinja rendering with ${input:...} refs."""
from __future__ import annotations

from pathlib import Path

import pytest

from loom.engine.models import Task
from loom.errors import RenderFailed
from loom.render.jinja import render_task_body


def _agent_folder(tmp_path: Path, template: str) -> Path:
    folder = tmp_path / "task"
    folder.mkdir()
    (folder / "prompt.md.j2").write_text(template)
    return folder


def test_renders_input(tmp_path):
    folder = _agent_folder(tmp_path, "Question: {{ input.q }}")
    out = render_task_body(Task(id="ask", kind="agent"), folder, {"q": "why"})
    assert "why" in out


def test_strict_undefined(tmp_path):
    folder = _agent_folder(tmp_path, "{{ input.missing }}")
    with pytest.raises(RenderFailed):
        render_task_body(Task(id="ask", kind="agent"), folder, {})


def test_workdir_root_scoped_for_child(tmp_path):
    folder = _agent_folder(
        tmp_path, "root workdir: {{ input.__loom.workdir }}"
    )
    out = render_task_body(
        Task(id="child/task", kind="agent", inlined_from_subgraph=True),
        folder,
        {"__loom": {"workdir": str(tmp_path / "root")}},
    )
    assert str(tmp_path / "root") in out

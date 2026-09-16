"""Gap 3: contract-local Jinja render context.

The renderer exposes ONLY ``input`` (the validated ``input.yaml``);
every attribute a template reads must be a declared field of the
task's ``io.yaml/input``. The two reserved engine-provided objects
(``__loom``, ``__task``) are ordinary opt-in properties — declared in
io.yaml and filled by the engine at dispatch. Templates access them
via ``input.__loom.workdir`` / ``input.__task.id``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from loom.engine.models import Task
from loom.errors import RenderFailed
from loom.render.jinja import render_task_body


def _agent_folder(tmp_path: Path, template: str) -> Path:
    folder = tmp_path / "task"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "prompt.md.j2").write_text(template)
    return folder


def test_only_declared_context_available(tmp_path: Path):
    """``input`` and declared reserved objects render."""
    folder = _agent_folder(
        tmp_path,
        "input={{ input.q }} workdir={{ input.__loom.workdir }}",
    )
    out = render_task_body(
        Task(id="ask", kind="agent"),
        folder,
        {"q": "why", "__loom": {"workdir": str(tmp_path / "work")}},
    )
    assert "input=why" in out
    assert f"workdir={tmp_path / 'work'}" in out


def test_absent_input_field_fails(tmp_path: Path):
    """StrictUndefined: an unknown key inside input aborts rendering."""
    folder = _agent_folder(tmp_path, "{{ input.missing_field }}")
    with pytest.raises(RenderFailed):
        render_task_body(
            Task(id="ask", kind="agent"), folder, {"other": "x"}
        )


@pytest.mark.parametrize(
    "name", ["run", "global", "vars", "task_output", "upstream"]
)
def test_undeclared_name_fails(tmp_path: Path, name: str):
    """Names outside the one-name contract are not in scope."""
    folder = _agent_folder(tmp_path, "{{ " + name + " }}")
    with pytest.raises(RenderFailed):
        render_task_body(Task(id="ask", kind="agent"), folder, {"x": 1})


@pytest.mark.parametrize("name", ["workdir", "task_workdir", "task"])
def test_bare_reserved_names_fail(tmp_path: Path, name: str):
    """The old ambient names are gone; a bare reference must abort."""
    folder = _agent_folder(tmp_path, "{{ " + name + " }}")
    with pytest.raises(RenderFailed):
        render_task_body(Task(id="ask", kind="agent"), folder, {"x": 1})


@pytest.mark.parametrize(
    "reserved,attr,payload",
    [
        ("__loom", "workdir", {"__loom": {"workdir": "/wd"}}),
        ("__task", "id", {"__task": {"id": "some-task"}}),
    ],
)
def test_reserved_objects_only_via_input(
    tmp_path: Path,
    reserved: str,
    attr: str,
    payload: dict,
):
    """Bare reserved names fail; dotted-through-input succeeds."""
    bare = _agent_folder(tmp_path / "bare", "{{ " + reserved + " }}")
    with pytest.raises(RenderFailed):
        render_task_body(Task(id="ask", kind="agent"), bare, payload)

    dotted = _agent_folder(
        tmp_path / "dotted",
        "value: {{ input." + reserved + "." + attr + " }}",
    )
    out = render_task_body(Task(id="ask", kind="agent"), dotted, payload)
    assert str(payload[reserved][attr]) in out


def test_cross_task_ref_not_available(tmp_path: Path):
    """No ``upstream`` / ``tasks`` dict — cross-task data reaches the
    task exclusively via graph.yaml ``input:`` mappings."""
    folder = _agent_folder(tmp_path, "{{ tasks['greet-user'].greeting }}")
    with pytest.raises(RenderFailed):
        render_task_body(Task(id="ask", kind="agent"), folder, {"x": 1})

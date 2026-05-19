"""Tests for engine.runner — placeholder resolution and lifecycle.

These cover the contracts the curator runtime relies on:

- ``EngineRun.resolve_value`` preserves native Python types (dict /
  list / scalar) when a string is exactly one ``${task:<id>[:field]}``
  placeholder, and falls back to YAML-stringified substitution for
  embedded placeholders.
- ``EngineRun.next_action`` returns the external batch WITHOUT
  marking it ``running``. Tasks transition to ``running`` only via
  the explicit ``commit_running`` call, so a render failure between
  ``next_action`` and ``commit_running`` leaves the batch pending
  for retry instead of stranding it.
- When the plan has non-terminal tasks but no ready successors,
  ``next_action`` returns None — the caller is expected to
  ``algorithm.is_done`` to disambiguate "done" from "stuck".
"""
from __future__ import annotations

from pathlib import Path

import yaml

from engine import EngineRun, algorithm, store
from engine.models import Plan, Task


# ── fixtures ───────────────────────────────────────────


def _start_run(tmp_path: Path, tasks: list[Task]) -> EngineRun:
    """Create a fresh EngineRun under tmp_path with the given tasks."""
    return EngineRun.start(
        base_dir=tmp_path,
        basename="test",
        plan_factory=lambda _wd: Plan(tasks=tasks),
    )


def _write_output(run: EngineRun, task_id: str, doc: dict) -> None:
    """Write ``output.yaml`` for a task and mark it done."""
    plan = store.load_plan(run.workdir)
    out = store.task_output_path(run.workdir, task_id, plan=plan)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    algorithm.mark_done(plan, task_id)
    store.save_plan(run.workdir, plan)


# ── resolve_value: type preservation ───────────────────


def test_resolve_value_whole_string_returns_native_dict(tmp_path: Path):
    """A string of the form ``${task:<id>:<field>}`` must resolve to
    the native Python value from the upstream output — dicts stay
    dicts, not YAML-dumped strings. This is the contract the summary
    extractor (and any future structured-access template) relies on.
    """
    run = _start_run(tmp_path, [
        Task(id="up",   kind="agent"),
        Task(id="down", kind="agent", depends_on=["up"]),
    ])
    _write_output(run, "up", {"obj": {"media": "article", "form": "blog"}})

    resolved = run.resolve_value("${task:up:obj}", task_id="down")
    assert isinstance(resolved, dict)
    assert resolved == {"media": "article", "form": "blog"}


def test_resolve_value_whole_string_returns_native_list(tmp_path: Path):
    """Lists also survive the round-trip without being stringified."""
    run = _start_run(tmp_path, [
        Task(id="up",   kind="agent"),
        Task(id="down", kind="agent", depends_on=["up"]),
    ])
    _write_output(run, "up", {"items": [1, 2, 3]})

    resolved = run.resolve_value("${task:up:items}", task_id="down")
    assert resolved == [1, 2, 3]


def test_resolve_value_whole_string_top_level_dict(tmp_path: Path):
    """Without a field path, the entire output document is returned."""
    run = _start_run(tmp_path, [
        Task(id="up",   kind="agent"),
        Task(id="down", kind="agent", depends_on=["up"]),
    ])
    _write_output(run, "up", {"a": 1, "b": [4, 5]})

    resolved = run.resolve_value("${task:up}", task_id="down")
    assert resolved == {"a": 1, "b": [4, 5]}


def test_resolve_value_embedded_placeholder_stringifies(tmp_path: Path):
    """An embedded placeholder (with surrounding text) must still
    string-coerce: the result is one string, not a structured value.
    This preserves the existing tool-task argv contract."""
    run = _start_run(tmp_path, [
        Task(id="up",   kind="agent"),
        Task(id="down", kind="agent", depends_on=["up"]),
    ])
    _write_output(run, "up", {"obj": {"media": "article"}})

    resolved = run.resolve_value(
        "prefix ${task:up:obj} suffix", task_id="down")
    assert isinstance(resolved, str)
    assert resolved.startswith("prefix ")
    assert resolved.endswith(" suffix")
    # The dict was YAML-dumped between the markers.
    assert "media: article" in resolved


def test_resolve_value_recurses_into_dict(tmp_path: Path):
    """A dict whose values are placeholders has each value resolved
    independently — whole-string entries become native, embedded
    entries stay strings. This is the exact pattern curator's
    summary task uses for ``upstream_outputs`` etc."""
    run = _start_run(tmp_path, [
        Task(id="up",   kind="agent"),
        Task(id="down", kind="agent", depends_on=["up"]),
    ])
    _write_output(run, "up", {"obj": {"k": "v"}, "n": 7})

    vars_dict = {
        "structured": "${task:up:obj}",
        "scalar":     "${task:up:n}",
        "embedded":   "n=${task:up:n}",
    }
    resolved = run.resolve_value(vars_dict, task_id="down")
    assert resolved["structured"] == {"k": "v"}
    # Scalar (int) round-trips through YAML resolution; the loaded
    # value is the int.
    assert resolved["scalar"] == 7
    assert resolved["embedded"] == "n=7"


def test_resolve_value_missing_field_returns_none(tmp_path: Path):
    """Asking for a field that does not exist in the upstream output
    yields None (the same behaviour as the embedded path's empty
    string, lifted to the native return)."""
    run = _start_run(tmp_path, [
        Task(id="up",   kind="agent"),
        Task(id="down", kind="agent", depends_on=["up"]),
    ])
    _write_output(run, "up", {"a": 1})

    assert run.resolve_value(
        "${task:up:missing}", task_id="down") is None


# ── next_action / commit_running lifecycle ─────────────


def test_next_action_does_not_commit_running(tmp_path: Path):
    """An external task in the returned batch stays ``pending``
    until ``commit_running`` is called explicitly. This is what
    lets the caller fail cleanly between picking and running."""
    run = _start_run(tmp_path, [Task(id="A", kind="agent")])
    action = run.next_action()
    assert action is not None
    assert [t["id"] for t in action.tasks] == ["A"]

    plan = store.load_plan(run.workdir)
    assert plan.get("A").status == "pending"


def test_next_action_then_commit_running_marks_running(tmp_path: Path):
    run = _start_run(tmp_path, [Task(id="A", kind="agent")])
    action = run.next_action()
    assert action is not None
    run.commit_running([t["id"] for t in action.tasks])

    plan = store.load_plan(run.workdir)
    assert plan.get("A").status == "running"


def test_next_action_returns_same_batch_until_commit(tmp_path: Path):
    """Calling next_action twice without commit_running yields the
    same batch — the tasks are still pending. Once committed, the
    batch is excluded (running tasks are not re-yielded)."""
    run = _start_run(tmp_path, [Task(id="A", kind="agent")])
    a1 = run.next_action()
    a2 = run.next_action()
    assert [t["id"] for t in a1.tasks] == ["A"]
    assert [t["id"] for t in a2.tasks] == ["A"]

    run.commit_running(["A"])
    a3 = run.next_action()
    # A is now running; not in the ready set; engine returns None.
    assert a3 is None


def test_next_action_returns_none_when_stuck(tmp_path: Path):
    """If a task is ``running`` (not terminal), and a downstream task
    is pending and depends on it, next_action returns None — the
    plan is not done, but engine has nothing to yield. Caller must
    check is_done to disambiguate."""
    run = _start_run(tmp_path, [
        Task(id="A", kind="agent"),
        Task(id="B", kind="agent", depends_on=["A"]),
    ])
    # Pick A and commit it to running.
    action = run.next_action()
    run.commit_running([t["id"] for t in action.tasks])

    # Now A is running, B is pending. next_action returns None.
    plan = store.load_plan(run.workdir)
    assert plan.get("A").status == "running"
    assert plan.get("B").status == "pending"
    assert run.next_action() is None
    # And the plan is NOT done — caller must distinguish.
    assert not algorithm.is_done(plan)

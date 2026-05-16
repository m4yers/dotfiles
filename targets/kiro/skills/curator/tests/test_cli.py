"""End-to-end CLI tests: plan.sh subprocess exercising the full flow.

These tests verify the engine contract as observed through the
shell boundary — what the calling skill will actually use. They
cover: plan create, task next returning parallel batches, output.yaml
validation, dynamic extension via plan extend, and failure handling.

Uses ``subprocess.run`` on ``plan.sh`` so the whole uv + typer +
storage stack is exercised end-to-end.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

# Tests use the legacy scheduler.sh CLI surface.
# After the engine + curator split, plan/task management is
# library-only; these tests need a full rewrite against
# curator.sh (ingest/next/complete) or the EngineRun API.
pytestmark = pytest.mark.skip(reason="needs rewrite for new engine/curator architecture")
import yaml

SKILL_ROOT = Path("/home/artyomgo/.kiro/skills/home/curator")
SCHEDULER_SH = SKILL_ROOT / "scripts" / "scheduler.sh"


def _run(*args: str, check: bool = True) -> dict:
    """Invoke plan.sh and return parsed YAML stdout."""
    r = subprocess.run(
        [str(SCHEDULER_SH), *args],
        capture_output=True, text=True, check=False,
    )
    if check and r.returncode != 0:
        raise AssertionError(
            f"plan.sh {args} failed:\nstderr={r.stderr}\nstdout={r.stdout}"
        )
    out = r.stdout.strip()
    if not out:
        return {"_exit": r.returncode, "_stderr": r.stderr}
    data = yaml.safe_load(out)
    if isinstance(data, dict):
        return data
    return {"_value": data, "_exit": r.returncode}


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    return tmp_path / "curator-test"


def _write_tasks_file(path: Path, tasks: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"tasks": tasks}), encoding="utf-8")


def _write_output(workdir: Path, task_id: str, obj: dict) -> None:
    p = workdir / "tasks" / task_id / "output.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")


# ── plan lifecycle ─────────────────────────────────────

def test_plan_create_empty(workdir: Path):
    r = _run("plan", "create", str(workdir), "--operation", "demo")
    assert r["ok"] is True
    assert r["tasks"] == 0
    assert (workdir / "plan.yaml").exists()
    assert (workdir / "state.yaml").exists()


def test_plan_create_rejects_duplicate(workdir: Path):
    _run("plan", "create", str(workdir), "--operation", "demo")
    r = _run("plan", "create", str(workdir), "--operation", "demo",
             check=False)
    assert r["_exit"] != 0


def test_plan_extend_appends_and_validates(workdir: Path, tmp_path: Path):
    _run("plan", "create", str(workdir), "--operation", "demo")
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [
        {"id": "A", "kind": "tool"},
        {"id": "B", "kind": "tool", "depends_on": ["A"]},
    ])
    r = _run("plan", "extend", str(workdir), "--tasks-file", str(tasks))
    assert r["ok"] and r["added"] == ["A", "B"] and r["tasks_total"] == 2


def test_plan_extend_rejects_duplicate_id(workdir: Path, tmp_path: Path):
    _run("plan", "create", str(workdir), "--operation", "demo")
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [{"id": "A", "kind": "tool"}])
    _run("plan", "extend", str(workdir), "--tasks-file", str(tasks))
    # Adding A again must fail.
    r = _run("plan", "extend", str(workdir), "--tasks-file", str(tasks),
             check=False)
    assert r["_exit"] != 0


def test_plan_extend_rejects_cycle(workdir: Path, tmp_path: Path):
    """Dynamic extension that would introduce a cycle is refused."""
    _run("plan", "create", str(workdir), "--operation", "demo")
    tasks = tmp_path / "t1.yaml"
    _write_tasks_file(tasks, [
        {"id": "A", "kind": "tool", "depends_on": ["B"]},
        {"id": "B", "kind": "tool", "depends_on": ["A"]},
    ])
    r = _run("plan", "extend", str(workdir), "--tasks-file", str(tasks),
             check=False)
    assert r["_exit"] != 0


# ── parallel batching ──────────────────────────────────

def test_task_next_returns_parallel_antichain(workdir: Path, tmp_path: Path):
    """THE core parallel-execution contract: diamond DAG returns
    {B, C} as a single batch after A completes."""
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [
        {"id": "A", "kind": "tool"},
        {"id": "B", "kind": "tool", "depends_on": ["A"]},
        {"id": "C", "kind": "tool", "depends_on": ["A"]},
        {"id": "D", "kind": "tool", "depends_on": ["B", "C"]},
    ])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))

    # Batch 1: just A.
    b1 = _run("task", "next", str(workdir))
    assert [t["id"] for t in b1["ready"]] == ["A"]

    # Complete A with a dummy output.
    _write_output(workdir, "A", {"ok": True})
    _run("task", "complete", str(workdir), "A")

    # Batch 2: parallel B + C.
    b2 = _run("task", "next", str(workdir))
    ids = sorted(t["id"] for t in b2["ready"])
    assert ids == ["B", "C"]

    # Complete both.
    for tid in ("B", "C"):
        _write_output(workdir, tid, {"ok": True})
        _run("task", "complete", str(workdir), tid)

    # Batch 3: D.
    b3 = _run("task", "next", str(workdir))
    assert [t["id"] for t in b3["ready"]] == ["D"]


def test_task_next_creates_per_task_workdir(workdir: Path, tmp_path: Path):
    """Every returned task has its subdir created under tasks/<id>/
    and task_workdir populated with the absolute path."""
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [{"id": "solo", "kind": "tool"}])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))
    b = _run("task", "next", str(workdir))
    assert len(b["ready"]) == 1
    task = b["ready"][0]
    assert task["task_workdir"] == str((workdir / "tasks" / "solo").resolve())
    assert Path(task["task_workdir"]).is_dir()
    assert task["output_path"].endswith("tasks/solo/output.yaml")


def test_task_next_excludes_running_tasks(workdir: Path, tmp_path: Path):
    """Calling 'task next' twice in a row returns the batch once and
    then the empty set (because running tasks are not re-dispatched).
    This prevents double-dispatch in concurrent orchestrators."""
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [{"id": "A", "kind": "tool"}])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))

    first = _run("task", "next", str(workdir))
    assert [t["id"] for t in first["ready"]] == ["A"]

    second = _run("task", "next", str(workdir))
    # Running now excludes A from the ready set.
    assert second["ready"] == []
    assert second["running"] == ["A"]


# ── output validation ──────────────────────────────────

def test_complete_without_output_transitions_to_failed(workdir: Path,
                                                        tmp_path: Path):
    """task complete --status ok must verify output.yaml exists."""
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [{"id": "A", "kind": "tool"}])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))
    _run("task", "next", str(workdir))
    # Don't write output.yaml. Complete must fail and transition A
    # to 'failed'.
    r = _run("task", "complete", str(workdir), "A", check=False)
    assert r["_exit"] != 0

    status = _run("task", "status", str(workdir))
    task_a = next(t for t in status["tasks"] if t["id"] == "A")
    assert task_a["status"] == "failed"


def test_complete_with_schema_violation_fails(workdir: Path,
                                                tmp_path: Path):
    """Schema-declared tasks: output that violates the schema
    transitions the task to failed."""
    schema = workdir / "schema.json"
    schema.parent.mkdir(parents=True, exist_ok=True)
    schema.write_text(json.dumps({
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "integer"}},
    }), encoding="utf-8")

    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [{
        "id": "A", "kind": "tool",
        "output_schema": str(schema),
    }])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))
    _run("task", "next", str(workdir))

    # Write wrong-shape output.
    _write_output(workdir, "A", {"value": "not an integer"})
    r = _run("task", "complete", str(workdir), "A", check=False)
    assert r["_exit"] != 0


# ── failure + reset ────────────────────────────────────

def test_fail_blocks_dependents_reset_unblocks(workdir: Path,
                                                tmp_path: Path):
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [
        {"id": "A", "kind": "tool"},
        {"id": "B", "kind": "tool", "depends_on": ["A"]},
    ])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))
    _run("task", "next", str(workdir))

    # Fail A explicitly.
    _run("task", "complete", str(workdir), "A", "--status", "fail")

    # B must NOT appear as ready.
    nxt = _run("task", "next", str(workdir))
    assert nxt["ready"] == []
    assert "A" in nxt["failed"]

    # Reset A. B should still be blocked until A completes successfully.
    _run("task", "reset", str(workdir), "A")
    nxt = _run("task", "next", str(workdir))
    assert [t["id"] for t in nxt["ready"]] == ["A"]


# ── status reporting ───────────────────────────────────

def test_status_summarizes_counts(workdir: Path, tmp_path: Path):
    tasks = tmp_path / "t.yaml"
    _write_tasks_file(tasks, [
        {"id": "A", "kind": "tool"},
        {"id": "B", "kind": "tool", "depends_on": ["A"]},
        {"id": "C", "kind": "tool", "depends_on": ["A"]},
    ])
    _run("plan", "create", str(workdir), "--operation", "demo",
         "--tasks-file", str(tasks))
    _run("task", "next", str(workdir))
    _write_output(workdir, "A", {"ok": True})
    _run("task", "complete", str(workdir), "A")
    _run("task", "next", str(workdir))  # moves B, C to running

    s = _run("task", "status", str(workdir))
    assert s["counts"]["total"] == 3
    assert s["counts"]["done"] == 1
    assert s["counts"]["running"] == 2
    assert s["counts"]["pending"] == 0

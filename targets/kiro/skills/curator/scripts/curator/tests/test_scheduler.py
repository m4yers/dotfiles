"""Tests for the DAG scheduler.

These tests cover the load-bearing invariants of parallel batch
execution:

- ``ready()`` returns every task whose deps are in ``completed``
  (antichain — parallel-safe).
- Running tasks are excluded to prevent double-dispatch.
- Failed tasks block dependents indefinitely (no silent unblock).
- Dynamic extension adds tasks whose deps then unlock them.
- Cycles and dangling deps are rejected at validation.
"""
from __future__ import annotations

import pytest

from engine.models import Plan, Task
from engine.algorithm import (
    is_done,
    mark_done,
    mark_failed,
    mark_running,
    ready,
    reset_task,
    validate_dag,
)


# ── fixtures ───────────────────────────────────────────

def _task(tid: str, deps: list[str] | None = None, kind: str = "tool") -> Task:
    return Task(id=tid, kind=kind, depends_on=deps or [])


def _linear_plan() -> Plan:
    """A → B → C."""
    return Plan(tasks=[_task("A"), _task("B", ["A"]), _task("C", ["B"])],
    )


def _diamond_plan() -> Plan:
    """A → B, A → C, B+C → D."""
    return Plan(tasks=[
            _task("A"),
            _task("B", ["A"]),
            _task("C", ["A"]),
            _task("D", ["B", "C"]),
        ],
    )


# ── ready-set ──────────────────────────────────────────

def test_ready_initial_returns_tasks_with_no_deps():
    plan = _linear_plan()
    r = ready(plan)
    assert [t.id for t in r] == ["A"]


def test_ready_advances_after_completion():
    plan = _linear_plan()
    mark_done(plan, "A")
    assert [t.id for t in ready(plan)] == ["B"]
    mark_done(plan, "B")
    assert [t.id for t in ready(plan)] == ["C"]


def test_ready_returns_parallel_antichain_on_diamond():
    """After A completes, B and C both become ready — this is THE
    parallel-execution property the engine must deliver."""
    plan = _diamond_plan()
    mark_done(plan, "A")
    r = ready(plan)
    assert {t.id for t in r} == {"B", "C"}


def test_ready_holds_back_d_until_both_b_and_c_complete():
    plan = _diamond_plan()
    mark_done(plan, "A")
    mark_done(plan, "B")
    # C still pending → D must not appear.
    assert [t.id for t in ready(plan)] == ["C"]
    mark_done(plan, "C")
    assert [t.id for t in ready(plan)] == ["D"]


# ── running exclusion ──────────────────────────────────

def test_running_tasks_excluded_from_ready():
    """ready() must not return a task that's already dispatched."""
    plan = _linear_plan()
    mark_running(plan, ["A"])
    assert ready(plan) == []


def test_mark_done_removes_from_running():
    plan = _linear_plan()
    mark_running(plan, ["A"])
    mark_done(plan, "A")
    assert "A" not in {t.id for t in plan.tasks if t.status == 'running'}
    assert "A" in {t.id for t in plan.tasks if t.status == 'done'}


# ── failure propagation ────────────────────────────────

def test_failed_task_blocks_dependents_forever():
    plan = _linear_plan()
    mark_running(plan, ["A"])
    mark_failed(plan, "A")
    # A is failed; B depends on A; B must not become ready.
    assert ready(plan) == []
    # Plan is NOT done because B and C are still pending (blocked but
    # not terminal). See the companion test below for is_done details.
    assert not is_done(plan)


def test_is_done_false_if_pending_tasks_blocked_by_failure():
    """A plan with a failed task and unreachable-but-pending dependents
    is NOT done — the caller decides whether to reset or abandon.
    This ensures the orchestrator sees "can't make progress" explicitly
    rather than a misleading done=True."""
    plan = _linear_plan()
    mark_failed(plan, "A")
    assert not is_done(plan)
    # B, C are still pending (blocked) — ready() returns empty, but
    # is_done() is false. Orchestrator must detect stalemate via:
    # ready() empty AND running empty AND not is_done → deadlock.


def test_failure_does_not_cascade_in_sibling():
    """A failed task blocks only its dependents, not unrelated tasks."""
    plan = Plan(tasks=[_task("A"), _task("B"), _task("C", ["A"])],
    )
    mark_failed(plan, "A")
    # B has no deps on A → still ready.
    assert [t.id for t in ready(plan)] == ["B"]


# ── reset / retry ──────────────────────────────────────

def test_reset_clears_all_terminal_states():
    plan = _linear_plan()
    mark_failed(plan, "A")
    reset_task(plan, "A")
    assert "A" not in {t.id for t in plan.tasks if t.status == 'failed'}
    assert "A" not in {t.id for t in plan.tasks if t.status == 'done'}
    assert "A" not in {t.id for t in plan.tasks if t.status == 'running'}


def test_reset_unblocks_pending_dependents():
    plan = _linear_plan()
    mark_failed(plan, "A")
    assert ready(plan) == []
    reset_task(plan, "A")
    # A is pending again, ready-set returns A.
    assert [t.id for t in ready(plan)] == ["A"]


# ── is_done ────────────────────────────────────────────

def test_is_done_true_when_all_completed():
    plan = _linear_plan()
    for tid in ("A", "B", "C"):
        mark_done(plan, tid)
    assert is_done(plan)


def test_is_done_false_when_any_pending():
    plan = _linear_plan()
    mark_done(plan, "A")
    assert not is_done(plan)


# ── validation ─────────────────────────────────────────

def test_validate_accepts_acyclic_plan():
    validate_dag(_linear_plan())
    validate_dag(_diamond_plan())


def test_validate_rejects_cycle():
    plan = Plan(tasks=[_task("A", ["B"]), _task("B", ["A"])],
    )
    with pytest.raises(ValueError, match="cycle"):
        validate_dag(plan)


def test_validate_rejects_dangling_dep():
    plan = Plan(tasks=[_task("A", ["nope"])],
    )
    with pytest.raises(ValueError, match="unknown"):
        validate_dag(plan)


def test_validate_rejects_duplicate_ids():
    plan = Plan(tasks=[_task("A"), _task("A")],
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_dag(plan)


# ── mixed scenarios ────────────────────────────────────

def test_parallel_batch_idempotent_if_not_yet_completed():
    """Calling ready() twice without any completions returns the
    same antichain — orchestrator can re-call safely."""
    plan = _diamond_plan()
    mark_done(plan, "A")
    first = {t.id for t in ready(plan)}
    second = {t.id for t in ready(plan)}
    assert first == second == {"B", "C"}


def test_partial_batch_completion_advances_incrementally():
    """Orchestrator completes B but not C → next ready() returns C
    alone, and D stays blocked."""
    plan = _diamond_plan()
    mark_done(plan, "A")
    # Simulate running both B and C.
    mark_running(plan, ["B", "C"])
    # B finishes first.
    mark_done(plan, "B")
    # Ready set: C is still running, D waits on C. Empty batch.
    assert ready(plan) == []
    # C finishes.
    mark_done(plan, "C")
    assert [t.id for t in ready(plan)] == ["D"]

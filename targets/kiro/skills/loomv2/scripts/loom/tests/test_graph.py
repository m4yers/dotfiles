"""Single-entry / single-exit enforcement."""
from __future__ import annotations

import pytest

from loom.engine.models import LoomPlan, LoopBlock, Task
from loom.errors import MultipleEntriesError, MultipleExitsError
from loom.validate.graph import validate_single_entry_exit


def _plan(tasks):
    return LoomPlan(loom_root=".", tasks=tasks)


def test_mid_graph_latch_with_single_consumer_is_not_an_exit():
    """Regression: a latch's back-edge lives in the latch declaration,
    not the dep edge set — a mid-graph latch with one downstream
    consumer must not be counted as a second exit."""
    p = _plan([
        Task(id="boot", kind="tool"),
        Task(id="step", kind="agent", depends_on_all=["boot"],
             latch=LoopBlock(header="step", fuel=3)),
        Task(id="report", kind="tool", depends_on_all=["step"]),
    ])
    validate_single_entry_exit(p)


def test_canonical_hammock():
    p = _plan([
        Task(id="a", kind="tool"),
        Task(id="b", kind="tool", depends_on_all=["a"]),
        Task(id="c", kind="tool", depends_on_all=["b"]),
    ])
    validate_single_entry_exit(p)


def test_two_roots():
    p = _plan([
        Task(id="a", kind="tool"),
        Task(id="b", kind="tool"),
        Task(id="c", kind="tool", depends_on_all=["a", "b"]),
    ])
    with pytest.raises(MultipleEntriesError) as exc:
        validate_single_entry_exit(p)
    assert exc.value.remedy in str(exc.value)


def test_two_leaves():
    p = _plan([
        Task(id="a", kind="tool"),
        Task(id="b", kind="tool", depends_on_all=["a"]),
        Task(id="c", kind="tool", depends_on_all=["a"]),
    ])
    with pytest.raises(MultipleExitsError) as exc:
        validate_single_entry_exit(p)
    assert exc.value.remedy in str(exc.value)


def test_empty_plan_rejected():
    with pytest.raises(MultipleEntriesError):
        validate_single_entry_exit(_plan([]))

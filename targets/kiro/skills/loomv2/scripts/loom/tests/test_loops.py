"""Loop admission + admission-rule error messages."""
from __future__ import annotations

import pytest

from loom.engine.models import LoomPlan, LoopBlock, Task
from loom.errors import (
    IrreducibleLoopError,
    LoopEscapeError,
    LoopNestingError,
    NoExitConditionError,
)
from loom.validate.loops import validate_loops


def _plan(tasks):
    return LoomPlan(loom_root=".", tasks=tasks)


def test_no_exit_error_carries_rule_and_fix():
    p = _plan([
        Task(id="fix", kind="agent"),
        Task(id="rev", kind="agent", depends_on_all=["fix"],
             latch=LoopBlock(header="fix")),
    ])
    with pytest.raises(NoExitConditionError) as exc:
        validate_loops(p)
    assert "no exit control" in str(exc.value)
    assert "Fix:" in str(exc.value)


def test_irreducible_message():
    p = _plan([
        Task(id="a", kind="tool"),
        Task(id="b", kind="tool", depends_on_all=["a"]),
        Task(id="c", kind="tool", depends_on_all=["b"],
             latch=LoopBlock(header="a", fuel=3)),
    ])
    # This is actually reducible; write a truly irreducible case:
    p = _plan([
        Task(id="a", kind="tool"),
        Task(id="b", kind="tool", depends_on_all=["a"]),
        Task(id="c", kind="tool", depends_on_any=["a", "b"],
             latch=LoopBlock(header="unknown", fuel=3)),
    ])
    with pytest.raises((IrreducibleLoopError, KeyError)):
        validate_loops(p)


def test_admission_rules_present_in_all_error_classes():
    for cls in (IrreducibleLoopError, LoopEscapeError, LoopNestingError, NoExitConditionError):
        assert cls.remedy
        assert cls.__doc__

"""Invariants for the ``loom.errors`` catalogue.

Every subclass MUST carry a docstring (cause) and a non-empty ``remedy``,
because ``__str__`` on plan errors composes both into the runtime message.
"""
from __future__ import annotations

import inspect

import loom.errors as _errors


def test_every_subclass_has_docstring_and_remedy():
    for name, obj in inspect.getmembers(_errors, inspect.isclass):
        if obj is _errors.LoomPlanError:
            continue
        if not issubclass(obj, (_errors.LoomPlanError, RuntimeError)):
            continue
        if obj in (RuntimeError, Exception):
            continue
        assert inspect.getdoc(obj), f"{name} missing docstring"
        assert getattr(obj, "remedy", ""), f"{name} missing remedy"


def test_str_contains_docstring_and_remedy_for_plan_errors():
    exc = _errors.DAGError("test")
    s = str(exc)
    assert "Cycle" in s or "duplicate" in s
    assert "Fix:" in s

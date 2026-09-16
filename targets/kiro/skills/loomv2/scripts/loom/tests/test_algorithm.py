"""Ready-set and cascade-skip semantics."""
from __future__ import annotations

from loom.engine.algorithm import cascade_skip, ready_tasks
from loom.engine.models import LoomPlan, Task


def test_ready_when_deps_done():
    a = Task(id="a", kind="tool", status="done")
    b = Task(id="b", kind="tool", depends_on_all=["a"])
    plan = LoomPlan(loom_root=".", tasks=[a, b])
    ready = [t.id for t in ready_tasks(plan)]
    assert "b" in ready


def test_cascade_skip_all():
    a = Task(id="a", kind="tool", status="skipped")
    b = Task(id="b", kind="tool", depends_on_all=["a"])
    plan = LoomPlan(loom_root=".", tasks=[a, b])
    assert cascade_skip(plan, b) is True


def test_cascade_skip_any_all_skipped():
    a = Task(id="a", kind="tool", status="skipped")
    b = Task(id="b", kind="tool", status="skipped")
    c = Task(id="c", kind="tool", depends_on_any=["a", "b"])
    plan = LoomPlan(loom_root=".", tasks=[a, b, c])
    assert cascade_skip(plan, c) is True


def test_cascade_skip_any_mixed_no_skip():
    a = Task(id="a", kind="tool", status="skipped")
    b = Task(id="b", kind="tool", status="done")
    c = Task(id="c", kind="tool", depends_on_any=["a", "b"])
    plan = LoomPlan(loom_root=".", tasks=[a, b, c])
    assert cascade_skip(plan, c) is False


def test_namespaced_ids_uniform():
    a = Task(id="sub/a", kind="tool", status="done")
    b = Task(id="sub/b", kind="tool", depends_on_all=["sub/a"])
    plan = LoomPlan(loom_root=".", tasks=[a, b])
    assert [t.id for t in ready_tasks(plan)] == ["sub/b"]

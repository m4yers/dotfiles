"""Loop EXECUTION: latch decision, round storage, predicate eval, CLI drive.

Complements test_loops.py (admission validation only). Covers the
runtime half ported from loom v1: fuel decrement + persistence,
``while_`` evaluation, body re-arming, and per-round ``iter-NN/``
output storage.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.engine.models import LoomPlan, LoopBlock, Task
from loom.engine.predicate import build_predicate_context, desugar_predicate, eval_predicate
from loom.engine.loops import latch_continue


# ---- desugaring ----

@pytest.mark.parametrize("expr,expected", [
    ("${task:review}", 'task."review"'),
    ("${task:review:verdict}", 'task."review".verdict'),
    ("${task:review:verdict != 'approved'}", 'task."review".verdict != \'approved\''),
    ("${task:review@2:verdict}", 'task_iter."review"."2".verdict'),
    ("${task:review@05}", 'task_iter."review"."5"'),
    ("${task:review@prev:verdict}", 'task_iter."review"."prev".verdict'),
    ("${task:child-lint/lint-text:notes}", 'task."child-lint/lint-text".notes'),
    ("$${task:review}", "$${task:review}"),  # escape untouched
])
def test_desugar_predicate(expr: str, expected: str):
    assert desugar_predicate(expr) == expected


# ---- latch_continue decision table ----

def _loop_plan(tmp_path: Path, latch: LoopBlock) -> tuple[LoomPlan, Path]:
    plan = LoomPlan(loom_root=tmp_path, tasks=[
        Task(id="fix", kind="agent"),
        Task(id="review", kind="agent", depends_on_all=["fix"], latch=latch),
    ])
    return plan, tmp_path


def _write_output(workdir: Path, plan: LoomPlan, task_id: str, doc: dict) -> None:
    from loom.engine.store import begin_round, task_folder

    round_dir = begin_round(task_folder(workdir, plan, task_id))
    (round_dir / "output.yaml").write_text(yaml.safe_dump(doc))


def test_latch_continue_fuel_only(tmp_path: Path):
    plan, wd = _loop_plan(tmp_path, LoopBlock(header="fix", fuel=2))
    latch = plan.tasks[1]
    assert latch_continue(latch, plan, wd) == (True, 1)
    latch.latch.fuel = 1
    assert latch_continue(latch, plan, wd) == (False, 0)


def test_latch_continue_while_only(tmp_path: Path):
    plan, wd = _loop_plan(
        tmp_path, LoopBlock(header="fix", while_="${task:review:verdict != 'approved'}"))
    latch = plan.tasks[1]
    _write_output(wd, plan, "review", {"verdict": "rejected"})
    cont, fuel = latch_continue(latch, plan, wd)
    assert cont is True and fuel is None
    _write_output(wd, plan, "review", {"verdict": "approved"})
    cont, _ = latch_continue(latch, plan, wd)
    assert cont is False


def test_latch_continue_either_control_stops(tmp_path: Path):
    plan, wd = _loop_plan(
        tmp_path,
        LoopBlock(header="fix", fuel=1, while_="${task:review:verdict != 'approved'}"))
    latch = plan.tasks[1]
    _write_output(wd, plan, "review", {"verdict": "rejected"})
    cont, fuel = latch_continue(latch, plan, wd)  # while true, fuel exhausted
    assert cont is False and fuel == 0


def test_predicate_context_rounds_and_prev(tmp_path: Path):
    plan, wd = _loop_plan(tmp_path, LoopBlock(header="fix", fuel=5))
    _write_output(wd, plan, "review", {"verdict": "rejected"})
    _write_output(wd, plan, "review", {"verdict": "approved"})
    ctx = build_predicate_context(plan, wd)
    assert ctx["task"]["review"] == {"verdict": "approved"}  # latest round
    assert ctx["task_iter"]["review"]["0"] == {"verdict": "rejected"}
    assert ctx["task_iter"]["review"]["prev"] == {"verdict": "rejected"}
    ok, _ = eval_predicate("${task:review@prev:verdict} == 'rejected'", plan, wd)
    assert ok is True


def test_predicate_context_evaluator_relative_prev(tmp_path: Path):
    """@prev = previous iteration relative to the evaluator's round;
    null on the first iteration; final round for non-iterating readers."""
    plan, wd = _loop_plan(tmp_path, LoopBlock(header="fix", fuel=5))
    _write_output(wd, plan, "review", {"verdict": "rejected"})
    _write_output(wd, plan, "review", {"verdict": "approved"})

    # Header dispatching round 2 reads round 1.
    ctx = build_predicate_context(plan, wd, evaluator=("fix", 2))
    assert ctx["task_iter"]["review"]["prev"] == {"verdict": "approved"}
    # Header dispatching round 1 reads round 0.
    ctx = build_predicate_context(plan, wd, evaluator=("fix", 1))
    assert ctx["task_iter"]["review"]["prev"] == {"verdict": "rejected"}
    # First iteration: explicit null — nothing produced before it.
    ctx = build_predicate_context(plan, wd, evaluator=("fix", 0))
    assert ctx["task_iter"]["review"]["prev"] is None
    # Latch self-read after completing round 1: its round 0.
    ctx = build_predicate_context(plan, wd, evaluator=("review", 1))
    assert ctx["task_iter"]["review"]["prev"] == {"verdict": "rejected"}
    # Non-iterating evaluator after loop exit: the final result.
    ctx = build_predicate_context(plan, wd, evaluator=("publish", None))
    assert ctx["task_iter"]["review"]["prev"] == {"verdict": "approved"}


def test_latch_continue_while_prev_self_read(tmp_path: Path):
    """A latch while_ using @prev on itself compares against the round
    before the one that just finished."""
    plan, wd = _loop_plan(
        tmp_path,
        LoopBlock(header="fix",
                  while_="${task:review@prev:verdict} != 'approved'"))
    latch = plan.tasks[1]
    _write_output(wd, plan, "review", {"verdict": "approved"})
    _write_output(wd, plan, "review", {"verdict": "rejected"})
    # Just finished round 1; @prev = round 0 = approved → while_ false.
    cont, _ = latch_continue(latch, plan, wd)
    assert cont is False
    _write_output(wd, plan, "review", {"verdict": "rejected"})
    # Just finished round 2; @prev = round 1 = rejected → while_ true.
    cont, _ = latch_continue(latch, plan, wd)
    assert cont is True


def test_eval_predicate_error_raises(tmp_path: Path):
    """Broken JMESPath raises PredicateEvalError; only a clean false skips."""
    from loom.errors import PredicateEvalError

    plan, wd = _loop_plan(tmp_path, LoopBlock(header="fix", fuel=5))
    with pytest.raises(PredicateEvalError):
        eval_predicate("${task:review:][invalid}", plan, wd)


# ---- CLI drive: fuel-bounded tool self-loop ----

@pytest.fixture
def fuel_loop_root(tmp_path: Path) -> Path:
    """boot (tool entry) → grind (tool, self-latch fuel=3, exit)."""
    root = tmp_path / "loom"
    root.mkdir()

    def tool_task(name: str, pascal: str) -> None:
        d = root / name
        d.mkdir()
        (d / "io.yaml").write_text(yaml.safe_dump({
            "version": 1,
            "input": {"type": "object", "additionalProperties": False},
            "output": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"n": {"type": "integer"}},
                "required": ["n"],
            },
        }))
        (d / "io_types.py").write_text(
            "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
            "from dataclasses import dataclass\n"
            "from typing import ClassVar\n"
            "\n"
            "\n"
            "@dataclass\n"
            f"class {pascal}Input:\n"
            "    VERSION: ClassVar[int] = 1\n"
            "    @classmethod\n"
            "    def from_dict(cls, d): return cls()\n"
            "    def to_dict(self): return {}\n"
            "\n"
            "\n"
            "@dataclass\n"
            f"class {pascal}Output:\n"
            "    VERSION: ClassVar[int] = 1\n"
            "    n: int\n"
            "    @classmethod\n"
            "    def from_dict(cls, d): return cls(n=d['n'])\n"
            "    def to_dict(self): return {'n': self.n}\n"
        )
        (d / "tool.py").write_text(
            f"from io_types import {pascal}Input, {pascal}Output\n"
            "\n"
            f"def {name}(inp: {pascal}Input) -> {pascal}Output:\n"
            f"    return {pascal}Output(n=7)\n"
        )

    tool_task("boot", "Boot")
    tool_task("grind", "Grind")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "boot", "kind": "tool", "version": 1},
            {"id": "grind", "kind": "tool", "version": 1,
             "depends_on_all": ["boot"]},
        ],
        "latches": [
            {"task": "grind", "header": "grind", "fuel": 3},
        ],
    }))
    return root


def test_cli_fuel_loop_runs_three_rounds(fuel_loop_root: Path, tmp_path: Path, capsys):
    from loom.__main__ import main
    from loom._lifecycle import resume
    from loom.engine.store import completed_iter_indices, task_folder

    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(fuel_loop_root)]) == 0
    capsys.readouterr()

    # One next call drives the whole plan: boot, then three grind rounds.
    assert main(["runtime", "next", str(workdir)]) == 0
    doc = yaml.safe_load(capsys.readouterr().out)
    assert doc == {"done": True, "ready": []}

    runtime = resume(workdir)
    grind_folder = task_folder(workdir, runtime.plan, "grind")
    assert completed_iter_indices(grind_folder) == [0, 1, 2]
    # Fuel exhausted and persisted; rounds counted on the task.
    grind = next(t for t in runtime.plan.tasks if t.id == "grind")
    assert grind.latch.fuel == 0
    assert grind.iter == 2  # bumped once per re-arm
    assert grind.status == "done"
    # boot stays flat: no rounds for non-loop tasks.
    boot_folder = task_folder(workdir, runtime.plan, "boot")
    assert (boot_folder / "output.yaml").exists()
    assert completed_iter_indices(boot_folder) == []
    # task_output resolves to the latest completed round.
    assert runtime.task_output("grind") == {"n": 7}


def _write_tool(root: Path, name: str, pascal: str, out_field: str = "n") -> None:
    """Tool task with empty input and a single required output field."""
    d = root / name
    d.mkdir()
    (d / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {out_field: {"type": "integer"}},
            "required": [out_field],
        },
    }))
    (d / "io_types.py").write_text(
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "@dataclass\n"
        f"class {pascal}Input:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
        "\n"
        "\n"
        "@dataclass\n"
        f"class {pascal}Output:\n"
        "    VERSION: ClassVar[int] = 1\n"
        f"    {out_field}: int\n"
        "    @classmethod\n"
        f"    def from_dict(cls, d): return cls({out_field}=d['{out_field}'])\n"
        f"    def to_dict(self): return {{'{out_field}': self.{out_field}}}\n"
    )
    (d / "tool.py").write_text(
        f"from io_types import {pascal}Input, {pascal}Output\n"
        "\n"
        f"def {name.replace('-', '_')}(inp: {pascal}Input) -> {pascal}Output:\n"
        f"    return {pascal}Output({out_field}=7)\n"
    )


def test_cli_fuel_one_runs_single_round(tmp_path: Path, capsys):
    """fuel: 1 — the body executes exactly once and never re-arms."""
    from loom.__main__ import main
    from loom._lifecycle import resume
    from loom.engine.store import completed_iter_indices, task_folder

    root = tmp_path / "loom"
    root.mkdir()
    _write_tool(root, "boot", "Boot")
    _write_tool(root, "grind", "Grind")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "boot", "kind": "tool", "version": 1},
            {"id": "grind", "kind": "tool", "version": 1,
             "depends_on_all": ["boot"]},
        ],
        "latches": [
            {"task": "grind", "header": "grind", "fuel": 1},
        ],
    }))

    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    capsys.readouterr()
    assert main(["runtime", "next", str(workdir)]) == 0
    assert yaml.safe_load(capsys.readouterr().out) == {"done": True, "ready": []}

    runtime = resume(workdir)
    grind_folder = task_folder(workdir, runtime.plan, "grind")
    assert completed_iter_indices(grind_folder) == [0]
    grind = next(t for t in runtime.plan.tasks if t.id == "grind")
    assert grind.latch.fuel == 0
    assert grind.iter == 0  # never re-armed
    assert grind.status == "done"


@pytest.fixture
def while_loop_root(tmp_path: Path) -> Path:
    """boot → step (agent, self-latch, while_-only) → report (exit).

    ``step`` has no fuel; the loop runs while ``n < 5``. ``report`` maps
    an absolute round (`@2`) and the latest round from the loop body.
    """
    root = tmp_path / "loom"
    root.mkdir()
    _write_tool(root, "boot", "Boot")

    step = root / "step"
    step.mkdir()
    (step / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    }))
    (step / "prompt.md.j2").write_text("Produce the next n. {{ input }}\n")

    report = root / "report"
    report.mkdir()
    (report / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "early": {"type": "integer"},
                "latest": {"type": "integer"},
            },
            "required": ["early", "latest"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"delta": {"type": "integer"}},
            "required": ["delta"],
        },
    }))
    (report / "io_types.py").write_text(
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class ReportInput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    early: int\n"
        "    latest: int\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(early=d['early'], latest=d['latest'])\n"
        "    def to_dict(self): return {'early': self.early, 'latest': self.latest}\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class ReportOutput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    delta: int\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(delta=d['delta'])\n"
        "    def to_dict(self): return {'delta': self.delta}\n"
    )
    (report / "tool.py").write_text(
        "from io_types import ReportInput, ReportOutput\n"
        "\n"
        "def report(inp: ReportInput) -> ReportOutput:\n"
        "    return ReportOutput(delta=inp.latest - inp.early)\n"
    )

    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "boot", "kind": "tool", "version": 1},
            {"id": "step", "kind": "agent", "version": 1,
             "depends_on_all": ["boot"]},
            {"id": "report", "kind": "tool", "version": 1,
             "depends_on_all": ["step"],
             "input": {"early": "${task:step@2:n}",
                       "latest": "${task:step:n}"}},
        ],
        "latches": [
            {"task": "step", "header": "step",
             "while_": "${task:step:n} < `5`"},
        ],
    }))
    return root


def test_cli_while_loop_runs_five_rounds_and_maps_rounds(
    while_loop_root: Path, tmp_path: Path, capsys,
):
    """while_-only loop (no fuel) driven for five engine-armed rounds;
    a downstream mapping reads an absolute round (@2) and the latest."""
    from loom.__main__ import main
    from loom._lifecycle import resume
    from loom.builders import output_add
    from loom.engine.store import completed_iter_indices, task_folder

    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(while_loop_root)]) == 0
    capsys.readouterr()

    # Rounds 0..4: driver writes n=1..5; while_ (n < 5) re-arms after
    # n=1..4 and stops at n=5.
    for n in range(1, 6):
        assert main(["runtime", "next", str(workdir)]) == 0
        doc = yaml.safe_load(capsys.readouterr().out)
        assert doc["done"] is False
        assert [e["id"] for e in doc["ready"]] == ["step"]
        output_add(workdir, "step", [f"n={n}"])
        assert main(["runtime", "complete", str(workdir), "step"]) == 0
        capsys.readouterr()

    # Loop stopped; the tail tools run and the plan finishes.
    assert main(["runtime", "next", str(workdir)]) == 0
    assert yaml.safe_load(capsys.readouterr().out) == {"done": True, "ready": []}

    runtime = resume(workdir)
    step_folder = task_folder(workdir, runtime.plan, "step")
    assert completed_iter_indices(step_folder) == [0, 1, 2, 3, 4]
    step = next(t for t in runtime.plan.tasks if t.id == "step")
    assert step.latch.fuel is None
    assert step.iter == 4  # re-armed once per continued round
    assert step.status == "done"

    # Downstream mapping: @2 → round index 2 (n=3); bare ref → latest (n=5).
    report_folder = task_folder(workdir, runtime.plan, "report")
    materialised = yaml.safe_load((report_folder / "input.yaml").read_text())
    assert materialised == {"early": 3, "latest": 5}
    assert runtime.task_output("report") == {"delta": 2}
    assert runtime.task_output("step") == {"n": 5}

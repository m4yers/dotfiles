"""``skip_output``: engine-level defaulting of when-false tasks.

A task entry with ``when:`` + ``skip_output:`` completes as ``done``
with the declared document when the predicate is false — instead of
being ``skipped`` — so AND-dependents do not cascade-skip and
``${task:...}`` refs resolve against the default.
"""
from __future__ import annotations

import textwrap

import pytest
import yaml


def _seed_plan_tool(root):
    task = root / "plan"
    task.mkdir(parents=True)
    (task / "io.yaml").write_text(textwrap.dedent("""\
        version: 1
        input:
          type: object
          additionalProperties: false
          properties:
            n: {type: string}
          required: [n]
        output:
          type: object
          additionalProperties: false
          properties:
            question: {type: string}
          required: [question]
    """))
    (task / "tool.py").write_text(textwrap.dedent("""\
        from io_types import PlanInput, PlanOutput


        def plan(inp):
            return PlanOutput(question="" if inp.n == "0" else "why?")
    """))


def _seed_slot_agent(root):
    task = root / "slot"
    task.mkdir(parents=True)
    (task / "io.yaml").write_text(textwrap.dedent("""\
        version: 1
        input:
          type: object
          additionalProperties: false
          properties:
            question: {type: string}
          required: [question]
        output:
          type: object
          additionalProperties: false
          properties:
            findings: {type: string}
          required: [findings]
    """))
    (task / "prompt.md.j2").write_text("Answer: {{ input.question }}\n")


def _seed_join_tool(root):
    task = root / "join"
    task.mkdir(parents=True)
    (task / "io.yaml").write_text(textwrap.dedent("""\
        version: 1
        input:
          type: object
          additionalProperties: false
          properties:
            findings: {type: string}
          required: [findings]
        output:
          type: object
          additionalProperties: false
          properties:
            merged: {type: string}
          required: [merged]
    """))
    (task / "tool.py").write_text(textwrap.dedent("""\
        from io_types import JoinInput, JoinOutput


        def join(inp):
            return JoinOutput(merged=f"[{inp.findings}]")
    """))


def _gen_io_types(root):
    from loom.scaffold.task import io_python
    for name in ("plan", "join"):
        io_python(root, name)


def _graph(root, skip_output=True, with_when=True):
    entry = {
        "id": "slot", "kind": "agent", "version": 1,
        "depends_on_all": ["plan"],
        "input": {"question": "${task:plan:question}"},
    }
    if with_when:
        entry["when"] = "${task:plan:question} != ''"
    if skip_output:
        entry["skip_output"] = {"findings": ""}
    (root / "graph.yaml").write_text(yaml.safe_dump({"tasks": [
        {"id": "plan", "kind": "tool", "version": 1},
        entry,
        {"id": "join", "kind": "tool", "version": 1,
         "depends_on_all": ["slot"],
         "input": {"findings": "${task:slot:findings}"}},
    ]}, sort_keys=False))


def _drive(workdir, root, n):
    """Init and drive via the CLI main(); returns final plan statuses."""
    import subprocess, sys, os
    loom_sh = os.path.expanduser(
        "~/.kiro/skills/home/loomv2/scripts/loom.sh")
    from loom import init
    from loom.engine.store import task_folder

    runtime = init(workdir, loom_root=root)
    # seed entry input
    entry_folder = workdir / "tasks" / "01-plan"
    entry_folder.mkdir(parents=True, exist_ok=True)
    (entry_folder / "input.yaml").write_text(f"n: '{n}'\n")
    return runtime


def test_when_false_with_skip_output_completes_done(tmp_path):
    from loom.cli_run import cmd_next
    import loom.cli_run as cli
    from loom import init

    root = tmp_path / "loom"
    _seed_plan_tool(root); _seed_slot_agent(root); _seed_join_tool(root)
    _gen_io_types(root); _graph(root)

    wd = tmp_path / "wd"
    runtime = init(wd, loom_root=root)
    (wd / "tasks" / "01-plan").mkdir(parents=True, exist_ok=True)
    (wd / "tasks" / "01-plan" / "input.yaml").write_text("n: '0'\n")

    # drive: plan (tool) runs, slot's when is false -> defaulted done,
    # join (tool) runs against the default.
    for _ in range(4):
        batch = runtime.next()
        if batch is None:
            break
        for t in list(batch.tasks):
            # tool tasks: dispatch via cli helper
            from loom.cli_run import _run_tool
            _run_tool(runtime, wd, t["id"])

    statuses = {t.id: t.status for t in runtime.plan.tasks}
    assert statuses == {"plan": "done", "slot": "done", "join": "done"}
    out = yaml.safe_load((wd / "tasks" / "03-join" / "output.yaml").read_text())
    assert out["merged"] == "[]"          # join consumed the default
    skip = yaml.safe_load(
        (wd / "tasks" / "02-slot" / "skip-reason.yaml").read_text())
    assert skip["reason_kind"] == "when-false-defaulted"


def test_when_true_surfaces_agent_normally(tmp_path):
    from loom import init

    root = tmp_path / "loom"
    _seed_plan_tool(root); _seed_slot_agent(root); _seed_join_tool(root)
    _gen_io_types(root); _graph(root)

    wd = tmp_path / "wd"
    runtime = init(wd, loom_root=root)
    (wd / "tasks" / "01-plan").mkdir(parents=True, exist_ok=True)
    (wd / "tasks" / "01-plan" / "input.yaml").write_text("n: '1'\n")

    from loom.cli_run import _run_tool
    batch = runtime.next()
    assert [t["id"] for t in batch.tasks] == ["plan"]
    _run_tool(runtime, wd, "plan")
    batch = runtime.next()
    assert [t["id"] for t in batch.tasks] == ["slot"]   # surfaced, not defaulted


def test_skip_output_without_when_rejected(tmp_path):
    from loom import init
    from loom.errors import GraphYamlError

    root = tmp_path / "loom"
    _seed_plan_tool(root); _seed_slot_agent(root); _seed_join_tool(root)
    _gen_io_types(root); _graph(root, with_when=False)

    with pytest.raises(GraphYamlError, match="without `when`"):
        init(tmp_path / "wd", loom_root=root)


def test_schema_invalid_skip_output_rejected(tmp_path):
    from loom import init
    from loom.errors import GraphYamlError

    root = tmp_path / "loom"
    _seed_plan_tool(root); _seed_slot_agent(root); _seed_join_tool(root)
    _gen_io_types(root); _graph(root)
    # corrupt the default
    doc = yaml.safe_load((root / "graph.yaml").read_text())
    doc["tasks"][1]["skip_output"] = {"findings": 42}
    (root / "graph.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))

    with pytest.raises(GraphYamlError, match="does not validate"):
        init(tmp_path / "wd", loom_root=root)


def test_skip_output_survives_plan_yaml_roundtrip(tmp_path):
    """The CLI reloads plan.yaml between invocations; skip_output must
    survive the serialise/deserialise round-trip or the default never
    fires after the first process exit."""
    from loom import init
    from loom.engine.store import read_plan_yaml
    from loom.engine.models import Task

    root = tmp_path / "loom"
    _seed_plan_tool(root); _seed_slot_agent(root); _seed_join_tool(root)
    _gen_io_types(root); _graph(root)

    wd = tmp_path / "wd"
    init(wd, loom_root=root)
    plan = read_plan_yaml(wd)
    slot = next(t for t in plan.tasks if isinstance(t, Task) and t.id == "slot")
    assert slot.skip_output == {"findings": ""}


def test_skip_output_survives_subgraph_inlining():
    """Regression: _prefix_task must copy skip_output — inlined child
    slot tasks silently lost their defaults and were skipped (cascade-
    skipping their AND-dependents) instead of completing done."""
    from pathlib import Path
    from loom.engine.inline import _prefix_task
    from loom.engine.models import Task

    child = Task(id="slot", kind="agent", when="${task:plan:q} != ''",
                 skip_output={"findings": ""})
    prefixed = _prefix_task(child, "ov", "deadbeef", Path("/tmp"))
    assert prefixed.skip_output == {"findings": ""}
    assert prefixed.id == "ov/slot"

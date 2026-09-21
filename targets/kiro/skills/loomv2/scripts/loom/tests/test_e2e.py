"""End-to-end run of the hello-graph fixture.

Exercises tool + agent + human + subgraph tasks through init → next →
complete → done, asserting that the exit output.yaml equals the
whole-graph output and that visualise labels child tasks with
canonical addresses.

The fixture also declares a loop (``confirm`` latches back onto
``summarise``) and embeds the same child root twice (``child-lint``,
``child-relint``). The CLI run drives the loop for two rounds: a
``revise`` decision re-arms the body (per-round outputs land under
``iter-NN/``), an ``accept`` decision stops it and releases the tail.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.engine.reserved import _RUNTIME_SH


def test_hello_graph_loads(hello_graph: Path):
    from loom.plan import from_graph_yaml

    plan = from_graph_yaml(hello_graph / "loom")
    ids = {t.id for t in plan.tasks if hasattr(t, "id")}
    assert "greet-user" in ids
    assert "finalise" in ids


def test_hello_graph_latch_loads(hello_graph: Path):
    from loom.engine.models import Task
    from loom.plan import from_graph_yaml

    plan = from_graph_yaml(hello_graph / "loom")
    confirm = next(t for t in plan.tasks if isinstance(t, Task) and t.id == "confirm")
    assert confirm.latch is not None
    assert confirm.latch.header == "summarise"
    assert confirm.latch.fuel == 3
    assert "decision" in confirm.latch.while_


def test_hello_graph_composition_inlines(hello_graph: Path):
    from loom.engine.inline import expand_subgraphs
    from loom.engine.models import Task
    from loom.plan import from_graph_yaml

    plan = from_graph_yaml(hello_graph / "loom")
    composed = expand_subgraphs(plan)
    inlined = {
        t.id: t for t in composed.tasks
        if isinstance(t, Task) and t.inlined_from_subgraph
    }
    # Same child root inlined twice under distinct instance namespaces.
    assert "child-lint/lint-text" in inlined
    assert "child-relint/lint-text" in inlined
    uids = {t.instance_uid for t in inlined.values()}
    assert len(uids) == 2, "each instance gets its own instance_uid"
    # Parent deps on the instance ids are retargeted at each child exit.
    finalise = next(t for t in composed.tasks if isinstance(t, Task) and t.id == "finalise")
    assert "child-lint/lint-text" in finalise.depends_on_all
    assert "child-relint/lint-text" in finalise.depends_on_all


def test_hello_graph_loop_admission_and_body(hello_graph: Path, tmp_workdir: Path):
    from loom import init
    from loom.engine.loops import compute_dominators, natural_loop_body

    # init runs validate_loops on the composed plan — no LoomPlanError.
    runtime = init(tmp_workdir, loom_root=hello_graph / "loom")
    dom = compute_dominators(runtime.plan, "greet-user")
    body = natural_loop_body(runtime.plan, "summarise", "confirm", dom)
    assert body == {"summarise", "confirm"}


def test_hello_graph_latch_roundtrips_plan_yaml(hello_graph: Path, tmp_workdir: Path):
    from loom import init
    from loom._lifecycle import resume
    from loom.engine.models import Task

    init(tmp_workdir, loom_root=hello_graph / "loom")
    reloaded = resume(tmp_workdir)
    confirm = next(t for t in reloaded.plan.tasks if isinstance(t, Task) and t.id == "confirm")
    assert confirm.latch is not None
    assert confirm.latch.header == "summarise"
    assert confirm.latch.fuel == 3


def test_hello_graph_visualise_labels_addresses(hello_graph: Path, tmp_workdir: Path):
    from loom import init
    from loom.visualise import visualise

    runtime = init(tmp_workdir, loom_root=hello_graph / "loom")
    out = visualise(runtime.plan)
    # Inlined child tasks appear under their instance addresses.
    assert "child-lint/lint-text" in out
    assert "child-relint/lint-text" in out
    # Ref-instanced tasks carry an inline suffix pointing at the
    # shared folder (`<instance-id> → <ref>`).
    assert "summarise-quick → summarise" in out
    assert "summarise-formal → summarise" in out
    # banner-sh (tool.sh shell shim) appears alongside the python tools.
    assert "banner-sh" in out
    # Loop latch annotation for confirm → summarise.
    assert "↻ loop → summarise" in out
    # Rail-renderer legend line is present.
    assert "legend:" in out
    assert "all-dep" in out and "any-dep" in out
    # Rail glyphs: fan-out to child-lint / child-relint from greet-user
    # produces a branch row (a line with the box-drawing branch char).
    assert any("├" in line or "╭" in line for line in out.splitlines()), (
        "expected a fan-out rail row in:\n" + out
    )


def test_hello_graph_cli_end_to_end(hello_graph: Path, tmp_path: Path, capsys):
    """Drive the full graph through the CLI to done, looping once.

    Cross-task data flows through the graph.yaml ``input:`` mappings.
    Only the entry task (``greet-user``) is caller-seeded; every other
    task's ``input.yaml`` is materialised by the engine at dispatch
    from its mapping.
    """
    from loom._lifecycle import resume
    from loom.__main__ import main
    from loom.builders import output_add
    from loom.engine.store import completed_iter_indices, task_folder

    workdir = tmp_path / "run"

    def run(*argv: str) -> tuple[int, str]:
        rc = main(list(argv))
        return rc, capsys.readouterr().out

    def seed_input(task_id: str, data: dict) -> None:
        plan = resume(workdir).plan
        folder = task_folder(workdir, plan, task_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "input.yaml").write_text(yaml.safe_dump(data))

    def next_ready() -> list[dict]:
        rc, out = run("runtime", "next", str(workdir))
        assert rc == 0
        doc = yaml.safe_load(out)
        assert doc["done"] is False
        return doc["ready"]

    rc, _ = run("runtime", "init", str(workdir), "--loom-root", str(hello_graph / "loom"))
    assert rc == 0

    # Entry task alone is caller-seeded. All other tasks' input.yaml is
    # materialised from their graph.yaml `input:` mapping.
    greeting = "Hello, Ada!"
    seed_input("greet-user", {"name": "Ada"})

    ready = next_ready()
    assert {e["id"] for e in ready} == {"summarise", "summarise-quick", "summarise-formal"}
    ready_by_id = {e["id"]: e for e in ready}
    # All three ready entries are agent kind.
    assert all(e["kind"] == "agent" for e in ready)
    # Mapping materialised: summarise.input.yaml carries greeting and
    # the reserved __loom object (declared in summarise/io.yaml).
    summarise_entry = ready_by_id["summarise"]
    summarise_input = yaml.safe_load(Path(summarise_entry["input_path"]).read_text())
    assert summarise_input["greeting"] == greeting
    assert summarise_input["__loom"] == {"workdir": str(workdir), "runtime": str(_RUNTIME_SH)}
    assert greeting in Path(summarise_entry["prompt_path"]).read_text()
    # The two ref-instanced entries share `summarise/io.yaml` and
    # `summarise/prompt.md.j2` but land in per-instance workdirs with
    # per-instance materialised input.yaml drawn from their own
    # `input:` mappings.
    for inst_id in ("summarise-quick", "summarise-formal"):
        inst = ready_by_id[inst_id]
        inst_input = yaml.safe_load(Path(inst["input_path"]).read_text())
        assert inst_input["greeting"] == greeting
        assert inst_input["__loom"] == {
            "workdir": str(workdir),
            "runtime": str(_RUNTIME_SH),
        }
        # The prompt_path is a rendered copy under the instance's own
        # workdir (task_folder("<inst_id>")), not under summarise/.
        prompt_path = Path(inst["prompt_path"])
        assert f"{inst_id}" in str(prompt_path) or prompt_path.parent.name.endswith(inst_id)

    runtime = resume(workdir)
    assert runtime.task_output("greet-user") == {"greeting": greeting}
    # child-lint ran internally: its input.yaml was materialised from
    # the same mapping.
    lint_folder = task_folder(workdir, runtime.plan, "child-lint/lint-text")
    assert yaml.safe_load(
        (lint_folder / "input.yaml").read_text()
    ) == {"greeting": greeting}
    assert runtime.task_output("child-lint/lint-text")["issues_found"] == 0
    # banner-sh (tool.sh shell shim) also ran internally in the same
    # tool-batch; its output.yaml was written by the shim itself and
    # validated against banner-sh/io.yaml/output by runtime complete.
    banner_folder = task_folder(workdir, runtime.plan, "banner-sh")
    assert yaml.safe_load(
        (banner_folder / "input.yaml").read_text()
    ) == {"greeting": greeting}
    assert runtime.task_output("banner-sh") == {
        "banner": f"*** {greeting} ***"
    }

    # Complete the two ref instances up-front — they're independent of
    # the loop body and drive the downstream aggregate-summaries tool.
    quick_summary = "hi Ada"
    formal_summary = "Greeting acknowledged."
    output_add(workdir, "summarise-quick", [f"summary={quick_summary}"])
    rc, _ = run("runtime", "complete", str(workdir), "summarise-quick")
    assert rc == 0
    output_add(workdir, "summarise-formal", [f"summary={formal_summary}"])
    rc, _ = run("runtime", "complete", str(workdir), "summarise-formal")
    assert rc == 0

    # ---- loop round 0: summary rejected ----
    draft = "Some greeting."
    output_add(workdir, "summarise", [f"summary={draft}"])
    rc, _ = run("runtime", "complete", str(workdir), "summarise")
    assert rc == 0

    ready = next_ready()
    assert [e["id"] for e in ready] == ["confirm"]
    confirm_input = yaml.safe_load(Path(ready[0]["input_path"]).read_text())
    assert confirm_input["summary"] == draft
    assert confirm_input["__loom"] == {"workdir": str(workdir), "runtime": str(_RUNTIME_SH)}
    assert draft in Path(ready[0]["message_path"]).read_text()

    output_add(workdir, "confirm", ["decision=revise", "reason=too vague"])
    rc, _ = run("runtime", "complete", str(workdir), "confirm")
    assert rc == 0

    # The latch fired: fuel 3→2, while_ true (decision != accept), body
    # re-armed — summarise surfaces again for round 1.
    runtime = resume(workdir)
    confirm = next(t for t in runtime.plan.tasks if t.id == "confirm")
    assert confirm.latch.fuel == 2
    assert confirm.status == "pending"

    # ---- loop round 1: summary accepted ----
    summary = "A friendly greeting to Ada."
    ready = next_ready()
    assert [e["id"] for e in ready] == ["summarise"]
    output_add(workdir, "summarise", [f"summary={summary}"])
    rc, _ = run("runtime", "complete", str(workdir), "summarise")
    assert rc == 0

    ready = next_ready()
    assert [e["id"] for e in ready] == ["confirm"]

    output_add(workdir, "confirm", ["decision=accept"])
    rc, _ = run("runtime", "complete", str(workdir), "confirm")
    assert rc == 0

    # Loop stopped: fuel 2→1 persisted, latch stays done, tail released.
    # finalise + child-relint materialise their inputs from summarise +
    # confirm on the next dispatch.
    rc, out = run("runtime", "next", str(workdir))
    assert rc == 0
    assert yaml.safe_load(out) == {"done": True, "ready": []}

    runtime = resume(workdir)
    confirm = next(t for t in runtime.plan.tasks if t.id == "confirm")
    assert confirm.latch.fuel == 1
    assert confirm.status == "done"

    # Per-round outputs preserved under iter-NN/, latest round wins.
    confirm_folder = task_folder(workdir, runtime.plan, "confirm")
    assert completed_iter_indices(confirm_folder) == [0, 1]
    round0 = yaml.safe_load((confirm_folder / "iter-00" / "output.yaml").read_text())
    assert round0["decision"] == "revise"
    assert runtime.task_output("confirm")["decision"] == "accept"
    assert runtime.task_output("summarise") == {"summary": summary}

    # Materialised input.yaml for finalise matches its declared mapping.
    finalise_folder = task_folder(workdir, runtime.plan, "finalise")
    assert yaml.safe_load(
        (finalise_folder / "input.yaml").read_text()
    ) == {"summary": summary, "decision": "accept"}

    # child-relint materialised from summarise.summary via the mapping.
    relint_folder = task_folder(workdir, runtime.plan, "child-relint/lint-text")
    assert yaml.safe_load(
        (relint_folder / "input.yaml").read_text()
    ) == {"greeting": summary}

    # The exit task's output.yaml is the whole-graph output.
    assert runtime.task_output("finalise") == {"message": f"[accept] {summary}"}
    relint = runtime.task_output("child-relint/lint-text")
    assert relint["notes"] == f"Linted {len(summary)} chars."



# ---- ref-instancing end-to-end fan-out ------------------------------


def _write_fanout_tool(
    folder: Path,
    name: str,
    input_schema: dict,
    output_schema: dict,
    body: str,
) -> None:
    from loom.naming import pascal_case_task_name

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": input_schema,
        "output": output_schema,
    }))
    pascal = pascal_case_task_name(name)
    in_fields = list(input_schema.get("properties", {}).keys())
    out_fields = list(output_schema.get("properties", {}).keys())
    lines = [
        "from dataclasses import dataclass",
        "from typing import ClassVar",
        "",
        "",
        f"@dataclass",
        f"class {pascal}Input:",
        "    VERSION: ClassVar[int] = 1",
    ]
    for f in in_fields:
        lines.append(f"    {f}: str")
    if not in_fields:
        lines.append("    pass")
    lines += [
        "    @classmethod",
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {in_fields!r}}})",
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {in_fields!r}}}",
        "",
        "",
        f"@dataclass",
        f"class {pascal}Output:",
        "    VERSION: ClassVar[int] = 1",
    ]
    for f in out_fields:
        lines.append(f"    {f}: str")
    lines += [
        "    @classmethod",
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {out_fields!r}}})",
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {out_fields!r}}}",
    ]
    (folder / "io_types.py").write_text("\n".join(lines) + "\n")
    (folder / "tool.py").write_text(body)


def test_ref_instancing_fanout_end_to_end(tmp_path: Path):
    """Fan-out graph: three ref-instanced agent tasks in parallel, each
    with its own input seed, a downstream aggregator that reads all
    three, and a final assertion that each instance's output.yaml
    lives under its own instance-id workdir with correct content.
    """
    from loom.__main__ import main
    from loom._lifecycle import resume
    from loom.builders import output_add
    from loom.engine.store import task_folder

    root = tmp_path / "loom"
    # seed → emits q1/q2/q3.
    _write_fanout_tool(
        root / "seed",
        "seed",
        {"type": "object", "additionalProperties": False},
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "q1": {"type": "string"},
                "q2": {"type": "string"},
                "q3": {"type": "string"},
            },
            "required": ["q1", "q2", "q3"],
        },
        "from io_types import SeedInput, SeedOutput\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(q1='alpha', q2='beta', q3='gamma')\n",
    )
    # Shared agent folder.
    research = root / "research"
    research.mkdir()
    (research / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    }))
    (research / "prompt.md.j2").write_text("Q: {{ input.question }}\n")

    # Aggregator reads all three instances.
    _write_fanout_tool(
        root / "aggregate",
        "aggregate",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "a1": {"type": "string"},
                "a2": {"type": "string"},
                "a3": {"type": "string"},
            },
            "required": ["a1", "a2", "a3"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"combined": {"type": "string"}},
            "required": ["combined"],
        },
        "from io_types import AggregateInput, AggregateOutput\n"
        "def aggregate(inp: AggregateInput) -> AggregateOutput:\n"
        "    return AggregateOutput(combined=f'{inp.a1}|{inp.a2}|{inp.a3}')\n",
    )

    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "research-q1", "kind": "agent", "version": 1,
             "ref": "research", "depends_on_all": ["seed"],
             "input": {"question": "${task:seed:q1}"}},
            {"id": "research-q2", "kind": "agent", "version": 1,
             "ref": "research", "depends_on_all": ["seed"],
             "input": {"question": "${task:seed:q2}"}},
            {"id": "research-q3", "kind": "agent", "version": 1,
             "ref": "research", "depends_on_all": ["seed"],
             "input": {"question": "${task:seed:q3}"}},
            {"id": "aggregate", "kind": "tool", "version": 1,
             "depends_on_all": ["research-q1", "research-q2", "research-q3"],
             "input": {
                 "a1": "${task:research-q1:answer}",
                 "a2": "${task:research-q2:answer}",
                 "a3": "${task:research-q3:answer}",
             }},
        ],
    }))

    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    # First next(): seed runs internally, three agents surface in parallel.
    from loom.__main__ import main as _main
    from io import StringIO
    import sys

    buf = StringIO()
    stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = _main(["runtime", "next", str(workdir)])
    finally:
        sys.stdout = stdout
    assert rc == 0
    doc = yaml.safe_load(buf.getvalue())
    assert doc["done"] is False
    surfaced = {e["id"] for e in doc["ready"]}
    assert surfaced == {"research-q1", "research-q2", "research-q3"}
    # Each instance's input.yaml was materialised from its OWN mapping.
    runtime = resume(workdir)
    for inst_id, seed_val in (
        ("research-q1", "alpha"),
        ("research-q2", "beta"),
        ("research-q3", "gamma"),
    ):
        folder = task_folder(workdir, runtime.plan, inst_id)
        got = yaml.safe_load((folder / "input.yaml").read_text())
        assert got == {"question": seed_val}

    # Complete each instance with a distinct answer.
    answers = {"research-q1": "A1", "research-q2": "A2", "research-q3": "A3"}
    for inst_id, answer in answers.items():
        output_add(workdir, inst_id, [f"answer={answer}"])
        assert main(["runtime", "complete", str(workdir), inst_id]) == 0

    # Second next(): aggregate runs internally (tool). done=True.
    buf2 = StringIO()
    sys.stdout = buf2
    try:
        rc = _main(["runtime", "next", str(workdir)])
    finally:
        sys.stdout = stdout
    assert rc == 0
    final = yaml.safe_load(buf2.getvalue())
    assert final == {"done": True, "ready": []}

    runtime = resume(workdir)
    # Each instance's output.yaml lives under its own instance-id workdir.
    for inst_id, expected in answers.items():
        folder = task_folder(workdir, runtime.plan, inst_id)
        assert (folder / "output.yaml").exists()
        assert yaml.safe_load((folder / "output.yaml").read_text()) == {"answer": expected}
        # The workdir name is anchored on the instance id, not the shared folder.
        assert folder.name.endswith(inst_id)
    # Aggregator saw all three instance outputs.
    assert runtime.task_output("aggregate") == {"combined": "A1|A2|A3"}

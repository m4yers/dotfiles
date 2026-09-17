"""Gap 2: graph.yaml ``input:`` mapping resolution + strict validation.

Covers:

  - Mapping resolves upstream outputs into the task's materialised
    input.yaml at dispatch.
  - Strict both-direction validation: absent required field OR
    undeclared extra field raises InputSchemaError and writes
    schema-error.yaml with ``phase: input``.
  - Per-round @prev references land the previous round's output.
  - Dual-instance subgraph wiring: two subgraph() calls with different
    parent-side mappings drive the same child root independently.
  - Static validator rejects mapping refs to tasks the entry cannot
    reach through its deps.
"""
from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
import yaml


# ---- fixtures ----

_MAP_LOOM_YAML = {
    "seed_output": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"n": {"type": "integer"}},
        "required": ["n"],
    },
    "square_input": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"n": {"type": "integer"}},
        "required": ["n"],
    },
    "square_output": {
        "type": "object",
        "additionalProperties": False,
        "properties": {"m": {"type": "integer"}},
        "required": ["m"],
    },
}


def _write_tool_task(folder: Path, name: str, input_schema, output_schema, body: str) -> None:
    from loom.naming import pascal_case_task_name

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": input_schema,
        "output": output_schema,
    }))
    pascal = pascal_case_task_name(name)
    fields_in = list(input_schema.get("properties", {}).keys())
    fields_out = list(output_schema.get("properties", {}).keys())

    lines = [
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit",
        "from dataclasses import dataclass",
        "from typing import ClassVar",
        "",
        "",
        "@dataclass",
        f"class {pascal}Input:",
        "    VERSION: ClassVar[int] = 1",
    ]
    for f in fields_in:
        lines.append(f"    {f}: int")
    if not fields_in:
        lines.append("    pass")
    lines += [
        "    @classmethod",
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {fields_in!r}}})",
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {fields_in!r}}}",
        "",
        "",
        "@dataclass",
        f"class {pascal}Output:",
        "    VERSION: ClassVar[int] = 1",
    ]
    for f in fields_out:
        lines.append(f"    {f}: int")
    lines += [
        "    @classmethod",
        f"    def from_dict(cls, d): return cls(**{{k: d[k] for k in {fields_out!r}}})",
        f"    def to_dict(self): return {{k: getattr(self, k) for k in {fields_out!r}}}",
    ]
    (folder / "io_types.py").write_text("\n".join(lines) + "\n")
    (folder / "tool.py").write_text(body)


@pytest.fixture
def two_tool_loom(tmp_path: Path) -> Path:
    """seed → square. `square` reads `n` from seed via mapping."""
    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        _MAP_LOOM_YAML["seed_output"],
        "from io_types import SeedInput, SeedOutput\n"
        "\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(n=7)\n",
    )
    _write_tool_task(
        root / "square", "square",
        _MAP_LOOM_YAML["square_input"],
        _MAP_LOOM_YAML["square_output"],
        "from io_types import SquareInput, SquareOutput\n"
        "\n"
        "def square(inp: SquareInput) -> SquareOutput:\n"
        "    return SquareOutput(m=inp.n * inp.n)\n",
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "square", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"n": "${task:seed:n}"}},
        ],
    }))
    return root


# ---- happy path ----

def test_mapping_resolves_and_materialises_input(two_tool_loom: Path, tmp_path: Path):
    from loom import init
    from loom.__main__ import main
    from loom.engine.store import task_folder

    workdir = tmp_path / "run"
    runtime = init(workdir, loom_root=two_tool_loom)
    assert main(["runtime", "next", str(workdir)]) == 0

    from loom._lifecycle import resume as _resume

    runtime = _resume(workdir)
    folder = task_folder(workdir, runtime.plan, "square")
    doc = yaml.safe_load((folder / "input.yaml").read_text())
    assert doc == {"n": 7}
    assert runtime.task_output("square") == {"m": 49}


# ---- strict validation: missing required ----

def _tool_with_input(root: Path, input_schema):
    """Standalone loom whose single task expects `input_schema`; mapping
    is empty (declared as `{}`) so the resolved dict is empty."""
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        _MAP_LOOM_YAML["seed_output"],
        "from io_types import SeedInput, SeedOutput\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(n=1)\n",
    )
    _write_tool_task(
        root / "target", "target",
        input_schema,
        {"type": "object", "additionalProperties": False},
        "from io_types import TargetInput, TargetOutput\n"
        "def target(inp: TargetInput) -> TargetOutput:\n"
        "    return TargetOutput()\n",
    )


def test_mapping_missing_required_raises_and_writes_diagnostic(tmp_path: Path):
    """Producer output.yaml legitimately omits a terminal key wired
    to a consumer's nullable required field — dispatch raises
    :class:`InputSchemaError` and writes ``schema-error.yaml`` with
    ``phase: input``.

    The static subtype pass passes because the consumer is nullable
    and the producer's schema marks the projected field as optional
    (``required`` at the producer's root does not include ``note``).
    Dispatch enforces the "no engine-inserted defaults" contract by
    refusing to invent a null the producer never emitted — the
    producer must emit an explicit null (via ``output add
    --set-json``) if the value is meant to be absent (io.md §6
    rule 5)."""
    from loom.__main__ import main
    from loom.builders import output_add
    from loom.engine.store import task_folder
    from loom._lifecycle import resume as _resume
    from loom.errors import InputSchemaError

    root = tmp_path / "loom"
    root.mkdir()
    # `seed` is an agent so the test drives its output.yaml directly.
    (root / "seed").mkdir()
    (root / "seed" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "n": {"type": "integer"},
                "note": {"type": ["string", "null"]},
            },
            "required": ["n"],
        },
    }))
    (root / "seed" / "prompt.md.j2").write_text("Produce n. {{ input }}\n")
    _write_tool_task(
        root / "target", "target",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"note": {"type": ["string", "null"]}},
            "required": ["note"],
        },
        {"type": "object", "additionalProperties": False},
        "from io_types import TargetInput, TargetOutput\n"
        "def target(inp: TargetInput) -> TargetOutput:\n"
        "    return TargetOutput()\n",
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "agent", "version": 1},
            {"id": "target", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"note": "${task:seed:note}"}},
        ],
    }))
    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    # Seed dispatches as agent; write its output missing `note`.
    assert main(["runtime", "next", str(workdir)]) == 0
    output_add(workdir, "seed", ["n=1"])
    assert main(["runtime", "complete", str(workdir), "seed"]) == 0
    # Target dispatch trips case (b): terminal key absent from producer.
    with pytest.raises(InputSchemaError):
        main(["runtime", "next", str(workdir)])

    runtime = _resume(workdir)
    folder = task_folder(workdir, runtime.plan, "target")
    err = yaml.safe_load((folder / "schema-error.yaml").read_text())
    assert err["phase"] == "input"
    assert err["task_id"] == "target"
    _validate_schema_error(err)


def test_mapping_undeclared_extra_raises(tmp_path: Path):
    from loom.__main__ import main
    from loom.errors import InputSchemaError

    root = tmp_path / "loom"
    root.mkdir()
    _tool_with_input(
        root,
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "target", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"],
             "input": {
                 "n": "${task:seed:n}",
                 "extra": "${task:seed:n}",
             }},
        ],
    }))
    workdir = tmp_path / "run"
    main(["runtime", "init", str(workdir), "--loom-root", str(root)])
    with pytest.raises(InputSchemaError):
        main(["runtime", "next", str(workdir)])


# ---- explicit-null pass-through (io.md §6 rule 5) ---------------------

def test_mapping_producer_emits_explicit_null_passes(tmp_path: Path):
    """Producer emits an explicit ``null`` (via ``output add
    --set-json``) into a field wired to a consumer input typed
    ``[X, null]``. Dispatch passes the null through unchanged; strict
    validation accepts it. The engine never invents a default — the
    producer's explicit null IS the value."""
    from loom.__main__ import main
    from loom.builders import output_add
    from loom.engine.store import task_folder
    from loom._lifecycle import resume as _resume

    root = tmp_path / "loom"
    root.mkdir()
    (root / "seed").mkdir()
    (root / "seed" / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"note": {"type": ["string", "null"]}},
            "required": ["note"],
        },
    }))
    (root / "seed" / "prompt.md.j2").write_text("Produce note. {{ input }}\n")
    _write_tool_task(
        root / "target", "target",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"note": {"type": ["string", "null"]}},
            "required": ["note"],
        },
        {"type": "object", "additionalProperties": False},
        "from io_types import TargetInput, TargetOutput\n"
        "def target(inp: TargetInput) -> TargetOutput:\n"
        "    return TargetOutput()\n",
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "agent", "version": 1},
            {"id": "target", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"note": "${task:seed:note}"}},
        ],
    }))
    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    assert main(["runtime", "next", str(workdir)]) == 0  # seed ready.
    # Write an explicit null via --set-json semantics.
    output_add(workdir, "seed", [(True, "note=null")])
    assert main(["runtime", "complete", str(workdir), "seed"]) == 0
    # Target dispatches; the null flows through.
    assert main(["runtime", "next", str(workdir)]) == 0
    runtime = _resume(workdir)
    folder = task_folder(workdir, runtime.plan, "target")
    doc = yaml.safe_load((folder / "input.yaml").read_text())
    assert doc == {"note": None}


# ---- per-round @prev ----

def test_mapping_prev_round_reference(tmp_path: Path):
    """Loop body reading @prev from prior round.

    Not exercised through the CLI (agent tasks require external
    completion). Uses ``resolve_task_input`` directly against a
    hand-built plan and pre-populated iter-NN/ outputs. Mirrors the
    real dispatch contract: loop-body tasks receive their ``iter-NN``
    round dir (``_dispatch_folder`` → ``begin_round``), and @prev is
    evaluator-relative — round k reads round k-1.
    """
    from loom.engine.mapping import resolve_task_input
    from loom.engine.models import LoomPlan, LoopBlock, Task
    from loom.engine.store import begin_round, task_folder

    plan = LoomPlan(loom_root=tmp_path, tasks=[
        Task(id="fix", kind="agent"),
        Task(
            id="review",
            kind="agent",
            depends_on_all=["fix"],
            latch=LoopBlock(header="fix", fuel=5),
            input_mapping={"note": "${task:fix@prev:note}"},
        ),
    ])
    workdir = tmp_path / "wd"
    fix_folder = task_folder(workdir, plan, "fix")
    d0 = begin_round(fix_folder)
    (d0 / "output.yaml").write_text(yaml.safe_dump({"note": "first"}))
    d1 = begin_round(fix_folder)
    (d1 / "output.yaml").write_text(yaml.safe_dump({"note": "second"}))

    # review completed round 0; its round-1 dispatch dir is fresh.
    review_folder = task_folder(workdir, plan, "review")
    r0 = begin_round(review_folder)
    (r0 / "output.yaml").write_text(yaml.safe_dump({"note": "r0"}))
    r1 = begin_round(review_folder)

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"note": {"type": "string"}},
        "required": ["note"],
    }
    doc = resolve_task_input(plan.tasks[1], plan, workdir, r1, schema)
    assert doc == {"note": "first"}  # previous iteration (round 0)


def _backedge_loop_plan(tmp_path: Path):
    """header reads latch@prev — the theory-form/theory-verdict shape."""
    from loom.engine.models import LoomPlan, LoopBlock, Task

    return LoomPlan(loom_root=tmp_path, tasks=[
        Task(
            id="form",
            kind="agent",
            input_mapping={"hint": "${task:verdict@prev:hint}"},
        ),
        Task(
            id="verdict",
            kind="agent",
            depends_on_all=["form"],
            latch=LoopBlock(header="form", fuel=5),
        ),
    ])


_NULLABLE_HINT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"hint": {"type": ["string", "null"]}},
    "required": ["hint"],
}


def test_mapping_prev_first_iteration_is_null(tmp_path: Path):
    """@prev on round 0 resolves to null when the schema allows it."""
    from loom.engine.mapping import resolve_task_input
    from loom.engine.store import begin_round, task_folder

    plan = _backedge_loop_plan(tmp_path)
    workdir = tmp_path / "wd"
    f0 = begin_round(task_folder(workdir, plan, "form"))

    doc = resolve_task_input(
        plan.tasks[0], plan, workdir, f0, _NULLABLE_HINT_SCHEMA
    )
    assert doc == {"hint": None}


def test_mapping_prev_first_iteration_rejected_by_schema(tmp_path: Path):
    """Round-0 null still fails strict validation for non-nullable fields."""
    from loom.engine.mapping import resolve_task_input
    from loom.engine.store import begin_round, task_folder
    from loom.errors import InputSchemaError

    plan = _backedge_loop_plan(tmp_path)
    workdir = tmp_path / "wd"
    f0 = begin_round(task_folder(workdir, plan, "form"))

    strict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"hint": {"type": "string"}},
        "required": ["hint"],
    }
    with pytest.raises(InputSchemaError):
        resolve_task_input(plan.tasks[0], plan, workdir, f0, strict)


def test_mapping_prev_later_rounds_get_previous_iteration(tmp_path: Path):
    """Round 1 of the header reads the latch's round-0 output — not null,
    not two rounds back."""
    from loom.engine.mapping import resolve_task_input
    from loom.engine.store import begin_round, task_folder

    plan = _backedge_loop_plan(tmp_path)
    workdir = tmp_path / "wd"
    v_folder = task_folder(workdir, plan, "verdict")
    v0 = begin_round(v_folder)
    (v0 / "output.yaml").write_text(yaml.safe_dump({"hint": "try-harder"}))
    form_folder = task_folder(workdir, plan, "form")
    f0 = begin_round(form_folder)
    (f0 / "output.yaml").write_text(yaml.safe_dump({}))
    f1 = begin_round(form_folder)

    doc = resolve_task_input(
        plan.tasks[0], plan, workdir, f1, _NULLABLE_HINT_SCHEMA
    )
    assert doc == {"hint": "try-harder"}


def test_mapping_prev_from_outside_loop_gets_final_round(tmp_path: Path):
    """A non-iterating consumer reading @prev after loop exit gets the
    loop's final (latest completed) result."""
    from loom.engine.mapping import resolve_task_input
    from loom.engine.models import LoomPlan, LoopBlock, Task
    from loom.engine.store import begin_round, task_folder

    plan = LoomPlan(loom_root=tmp_path, tasks=[
        Task(id="fix", kind="agent"),
        Task(
            id="review",
            kind="agent",
            depends_on_all=["fix"],
            latch=LoopBlock(header="fix", fuel=5),
        ),
        Task(
            id="publish",
            kind="agent",
            depends_on_all=["review"],
            input_mapping={"note": "${task:fix@prev:note}"},
        ),
    ])
    workdir = tmp_path / "wd"
    fix_folder = task_folder(workdir, plan, "fix")
    d0 = begin_round(fix_folder)
    (d0 / "output.yaml").write_text(yaml.safe_dump({"note": "first"}))
    d1 = begin_round(fix_folder)
    (d1 / "output.yaml").write_text(yaml.safe_dump({"note": "final"}))

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"note": {"type": "string"}},
        "required": ["note"],
    }
    doc = resolve_task_input(
        plan.tasks[2], plan, workdir, task_folder(workdir, plan, "publish"),
        schema,
    )
    assert doc == {"note": "final"}


# ---- dual-instance subgraph wiring ----

def test_dual_instance_subgraph_wires_independently(tmp_path: Path):
    """Same child root embedded twice with different parent-side mappings.

    Each embedding materialises its own input from the parent-supplied
    placeholder; the two child instances land distinct values.
    """
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.store import task_folder

    # Child: single "square" task.
    child_root = tmp_path / "child" / "loom"
    _write_tool_task(
        child_root / "square", "square",
        _MAP_LOOM_YAML["square_input"],
        _MAP_LOOM_YAML["square_output"],
        "from io_types import SquareInput, SquareOutput\n"
        "def square(inp: SquareInput) -> SquareOutput:\n"
        "    return SquareOutput(m=inp.n * inp.n)\n",
    )
    (child_root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "square", "kind": "tool", "version": 1}],
    }))

    # Parent: origin → (left-square, right-square) → sum. `origin` emits
    # both `a` and `b`; each subgraph reads one via its own mapping.
    parent_root = tmp_path / "parent" / "loom"
    _write_tool_task(
        parent_root / "origin", "origin",
        {"type": "object", "additionalProperties": False},
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        "from io_types import OriginInput, OriginOutput\n"
        "def origin(inp: OriginInput) -> OriginOutput:\n"
        "    return OriginOutput(a=3, b=4)\n",
    )
    _write_tool_task(
        parent_root / "sum", "sum",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"total": {"type": "integer"}},
            "required": ["total"],
        },
        "from io_types import SumInput, SumOutput\n"
        "def sum(inp: SumInput) -> SumOutput:\n"
        "    return SumOutput(total=inp.a + inp.b)\n",
    )
    (parent_root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "origin", "kind": "tool", "version": 1},
            {"id": "left", "kind": "subgraph", "version": 1,
             "root": "../../child/loom",
             "depends_on_all": ["origin"],
             "input": {"n": "${task:origin:a}"}},
            {"id": "right", "kind": "subgraph", "version": 1,
             "root": "../../child/loom",
             "depends_on_all": ["origin"],
             "input": {"n": "${task:origin:b}"}},
            {"id": "sum", "kind": "tool", "version": 1,
             "depends_on_all": ["left", "right"],
             "input": {
                 "a": "${task:left:m}",
                 "b": "${task:right:m}",
             }},
        ],
    }))

    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(parent_root)]) == 0
    assert main(["runtime", "next", str(workdir)]) == 0

    runtime = _resume(workdir)
    left = task_folder(workdir, runtime.plan, "left/square")
    right = task_folder(workdir, runtime.plan, "right/square")
    assert yaml.safe_load((left / "input.yaml").read_text()) == {"n": 3}
    assert yaml.safe_load((right / "input.yaml").read_text()) == {"n": 4}
    assert runtime.task_output("sum") == {"total": 3 * 3 + 4 * 4}


# ---- static validator: unknown ref rejected at init ----

def test_mapping_ref_to_undeclared_task_rejected_at_init(tmp_path: Path):
    from loom import init
    from loom.errors import ReferenceError

    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        _MAP_LOOM_YAML["seed_output"],
        "from io_types import SeedInput, SeedOutput\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(n=1)\n",
    )
    _write_tool_task(
        root / "target", "target",
        _MAP_LOOM_YAML["square_input"],
        {"type": "object", "additionalProperties": False},
        "from io_types import TargetInput, TargetOutput\n"
        "def target(inp: TargetInput) -> TargetOutput:\n"
        "    return TargetOutput()\n",
    )
    # `target` references `phantom` — a task that does not exist.
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "target", "kind": "tool", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"n": "${task:phantom:n}"}},
        ],
    }))
    workdir = tmp_path / "run"
    with pytest.raises(ReferenceError):
        init(workdir, loom_root=root)


# ---- helpers ----

_SCHEMA_ERROR_META = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "schemas" / "schema-error.yaml").read_text()
)


def _validate_schema_error(doc: dict) -> None:
    jsonschema.validate(doc, _SCHEMA_ERROR_META)


# ---- reserved engine-provided fields ----

def _write_agent_task(
    folder: Path,
    name: str,
    input_schema: dict,
    output_schema: dict,
    template: str,
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": input_schema,
        "output": output_schema,
    }))
    (folder / "prompt.md.j2").write_text(template)


def test_reserved_field_engine_filled(tmp_path: Path):
    """Engine fills ``__loom`` in input.yaml when declared in io.yaml,
    with no graph.yaml mapping wiring required."""
    from loom.__main__ import main
    from loom._lifecycle import resume as _resume
    from loom.engine.reserved import LoomMeta, _RUNTIME_SH
    from loom.engine.store import task_folder

    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        _MAP_LOOM_YAML["seed_output"],
        "from io_types import SeedInput, SeedOutput\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(n=1)\n",
    )
    _write_agent_task(
        root / "ask",
        "ask",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "n": {"type": "integer"},
                "__loom": {},
            },
            "required": ["n", "__loom"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
        "value: {{ input.n }} at {{ input.__loom.workdir }}\n",
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "ask", "kind": "agent", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"n": "${task:seed:n}"}},
        ],
    }))

    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(root)]) == 0
    assert main(["runtime", "next", str(workdir)]) == 0

    runtime = _resume(workdir)
    folder = task_folder(workdir, runtime.plan, "ask")
    doc = yaml.safe_load((folder / "input.yaml").read_text())
    assert doc["n"] == 1
    assert doc["__loom"] == LoomMeta(workdir=str(workdir), runtime=str(_RUNTIME_SH)).to_dict()
    assert doc["__loom"]["workdir"] == str(workdir)


def test_reserved_field_shadow_rejected_dispatch(tmp_path: Path):
    """A plan built in Python that bypasses static validate must still
    have dispatch reject a reserved mapping key."""
    from loom.engine.mapping import resolve_task_input
    from loom.engine.models import LoomPlan, Task
    from loom.errors import InputSchemaError

    task = Task(
        id="ask",
        kind="agent",
        depends_on_all=["seed"],
        input_mapping={"__loom": "${task:seed:x}"},
    )
    plan = LoomPlan(
        loom_root=tmp_path,
        tasks=[Task(id="seed", kind="tool"), task],
    )
    input_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "__loom": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"workdir": {"type": "string"}},
                "required": ["workdir"],
            },
        },
        "required": ["__loom"],
    }
    with pytest.raises(InputSchemaError) as exc:
        resolve_task_input(
            task, plan, tmp_path, tmp_path / "ask", input_schema
        )
    message = str(exc.value)
    assert "reserved" in message.lower()
    assert "references/io.md" in message


def test_reserved_field_shadow_rejected_static(tmp_path: Path):
    """Full ``$LOOM validate`` / ``loom.init`` path raises
    ``ReservedShadowError`` when a graph.yaml ``input:`` mapping wires
    a reserved name."""
    from loom import init
    from loom.errors import ReservedShadowError

    root = tmp_path / "loom"
    root.mkdir()
    _write_tool_task(
        root / "seed", "seed",
        {"type": "object", "additionalProperties": False},
        _MAP_LOOM_YAML["seed_output"],
        "from io_types import SeedInput, SeedOutput\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(n=1)\n",
    )
    _write_agent_task(
        root / "ask",
        "ask",
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "__loom": {},
            },
            "required": ["__loom"],
        },
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
        },
        "value: {{ input.__loom.workdir }}\n",
    )
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "ask", "kind": "agent", "version": 1,
             "depends_on_all": ["seed"],
             "input": {"__loom": "${task:seed:n}"}},
        ],
    }))
    workdir = tmp_path / "run"
    with pytest.raises(ReservedShadowError):
        init(workdir, loom_root=root)

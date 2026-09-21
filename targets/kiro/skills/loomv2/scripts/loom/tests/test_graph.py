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



# ---- ref field meta-schema tests ----------------------------------


def _validate_graph_yaml(doc: dict) -> None:
    """Meta-validate ``doc`` against ``schemas/graph.yaml``."""
    from pathlib import Path
    import jsonschema
    import yaml as _yaml

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "schemas"
        / "graph.yaml"
    )
    meta = _yaml.safe_load(schema_path.read_text())
    jsonschema.validate(doc, meta)


def test_ref_field_accepted_on_tool_agent_human():
    for kind in ("tool", "agent", "human"):
        _validate_graph_yaml({
            "tasks": [
                {"id": "seed", "kind": "tool", "version": 1},
                {"id": "one", "kind": kind, "version": 1, "ref": "shared"},
            ],
        })


def test_ref_rejected_on_subgraph_entry():
    import jsonschema

    doc = {
        "tasks": [
            {"id": "one", "kind": "subgraph", "version": 1,
             "root": "../other/loom", "ref": "shared"},
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        _validate_graph_yaml(doc)


def test_ref_must_match_kebab_pattern():
    import jsonschema

    for bad in ("Shared", "sh_ared", "-shared", "shared!"):
        doc = {
            "tasks": [
                {"id": "one", "kind": "tool", "version": 1, "ref": bad},
            ],
        }
        with pytest.raises(jsonschema.ValidationError):
            _validate_graph_yaml(doc)


def test_ref_instancing_example_from_schema_validates():
    """The instancing example bundled in ``schemas/graph.yaml``
    top-level ``examples:`` must meta-validate against the schema
    itself."""
    from pathlib import Path
    import yaml as _yaml

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "schemas"
        / "graph.yaml"
    )
    meta = _yaml.safe_load(schema_path.read_text())
    examples = meta.get("examples", [])
    # Find the instancing example — the one whose tasks share `ref`.
    ref_example = next(
        (ex for ex in examples
         if any(t.get("ref") for t in ex.get("tasks", []))),
        None,
    )
    assert ref_example is not None, "missing instancing example in schema"
    _validate_graph_yaml(ref_example)

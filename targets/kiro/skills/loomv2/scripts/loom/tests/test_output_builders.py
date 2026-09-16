"""`output add` builder: bracket path grammar + partial validation.

Regression suite for the two documented-but-broken behaviours hit by
the rca skill's human gates:

  - ``field[]`` appends a fresh list element; ``field[-1]`` addresses
    the last one (commands.md promised this; the parser treated the
    brackets as literal dict keys).
  - Incremental multi-call writes: per-add validation must not demand
    ``required`` fields that later calls will supply. Completeness is
    enforced by ``runtime complete``, which fully validates.

Wrong field names (``additionalProperties: false``) and wrong types
must still fail fast per add.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from loom.__main__ import main
from loom.builders import output_add
from loom.errors import OutputSchemaError


@pytest.fixture
def report_loom_root(tmp_path: Path) -> Path:
    """Single agent task with the rca existing-timeline output shape."""
    root = tmp_path / "loom"
    gate = root / "gate"
    gate.mkdir(parents=True)
    (gate / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object"},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "required": ["narrative", "decision", "timeline"],
            "properties": {
                "narrative": {"type": "string"},
                "decision": {"type": "string", "enum": ["continue", "stop"]},
                "timeline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["date", "summary"],
                        "properties": {
                            "date": {"type": "string"},
                            "summary": {"type": "string"},
                        },
                    },
                },
            },
        },
    }))
    (gate / "prompt.md.j2").write_text("go: {{ input }}\n")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [{"id": "gate", "kind": "agent", "version": 1}],
    }))
    return root


@pytest.fixture
def gate_workdir(report_loom_root: Path, tmp_path: Path) -> Path:
    workdir = tmp_path / "run"
    assert main(["runtime", "init", str(workdir), "--loom-root", str(report_loom_root)]) == 0
    assert main(["runtime", "next", str(workdir)]) == 0
    return workdir


def _output_doc(workdir: Path) -> dict:
    return yaml.safe_load((workdir / "tasks" / "01-gate" / "output.yaml").read_text())


def test_append_and_last_element_across_calls(gate_workdir: Path):
    """The exact multi-call pattern the rca prompts document."""
    output_add(gate_workdir, "gate", [
        "narrative=two events",
        "decision=continue",
    ])
    output_add(gate_workdir, "gate", [
        "timeline[].date=2026-09-14T15:51:00Z",
        "timeline[-1].summary=ticket opened",
    ])
    output_add(gate_workdir, "gate", [
        "timeline[].date=2026-09-16T08:09:55Z",
        "timeline[-1].summary=sla breach filed",
    ])
    doc = _output_doc(gate_workdir)
    assert doc["timeline"] == [
        {"date": "2026-09-14T15:51:00Z", "summary": "ticket opened"},
        {"date": "2026-09-16T08:09:55Z", "summary": "sla breach filed"},
    ]
    # Completeness gate still enforced end-to-end.
    assert main(["runtime", "complete", str(gate_workdir), "gate"]) == 0


def test_partial_add_does_not_demand_required_fields(gate_workdir: Path):
    output_add(gate_workdir, "gate", ["narrative=only this so far"])
    assert _output_doc(gate_workdir) == {"narrative": "only this so far"}


def test_complete_still_rejects_incomplete_output(gate_workdir: Path):
    output_add(gate_workdir, "gate", ["narrative=missing the rest"])
    with pytest.raises(OutputSchemaError):
        main(["runtime", "complete", str(gate_workdir), "gate"])


def test_wrong_field_name_fails_fast(gate_workdir: Path):
    with pytest.raises(OutputSchemaError):
        output_add(gate_workdir, "gate", ["narative=typo"])


def test_wrong_nested_field_name_fails_fast(gate_workdir: Path):
    with pytest.raises(OutputSchemaError):
        output_add(gate_workdir, "gate", [
            "timeline[].date=2026-09-14",
            "timeline[-1].source=not-in-schema",
        ])


def test_wrong_type_fails_fast(gate_workdir: Path):
    # _coerce turns "5" into an int; narrative wants a string.
    with pytest.raises(OutputSchemaError):
        output_add(gate_workdir, "gate", ["narrative=5"])


def test_explicit_bracket_index_and_dotted_numeric(gate_workdir: Path):
    output_add(gate_workdir, "gate", ["timeline[0].date=via-bracket"])
    output_add(gate_workdir, "gate", ["timeline.0.summary=via-dotted"])
    assert _output_doc(gate_workdir)["timeline"] == [
        {"date": "via-bracket", "summary": "via-dotted"},
    ]


def test_negative_index_on_empty_list_is_clear_error(gate_workdir: Path):
    with pytest.raises(OutputSchemaError, match="append first"):
        output_add(gate_workdir, "gate", ["timeline[-1].date=nope"])


def test_malformed_bracket_segment_is_clear_error(gate_workdir: Path):
    with pytest.raises(OutputSchemaError, match="bad path"):
        output_add(gate_workdir, "gate", ["timeline[x].date=nope"])

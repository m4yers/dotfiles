"""End-to-end drive of the ``runtime init`` / ``runtime next`` / ``runtime complete`` CLI loop.

Exercises a two-task graph: a ``tool`` entry (executed internally by
``runtime next``) followed by an ``agent`` exit (surfaced in ``ready``,
completed after the caller writes ``output.yaml``).
"""
from __future__ import annotations

from pathlib import Path

import jsonschema
import pytest
import yaml

from loom.__main__ import main
from loom.builders import output_add


# schemas/ lives at the skill root; tests live at scripts/loom/tests/.
_NEXT_SCHEMA = yaml.safe_load(
    (Path(__file__).resolve().parents[3] / "schemas" / "next.yaml").read_text()
)


def _parse_next(out: str) -> dict:
    """Parse `$LOOM runtime next` stdout and validate against schemas/next.yaml."""
    doc = yaml.safe_load(out)
    jsonschema.validate(doc, _NEXT_SCHEMA)
    return doc


@pytest.fixture
def cli_loom_root(tmp_path: Path) -> Path:
    """Two-task loom: tool entry → agent exit."""
    root = tmp_path / "loom"
    root.mkdir()

    seed = root / "seed"
    seed.mkdir()
    (seed / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object"},
        "output": {
            "type": "object",
            "properties": {"n": {"type": "integer"}},
            "required": ["n"],
        },
    }))
    (seed / "io_types.py").write_text(
        "# generated from io.yaml v1 by $LOOM task io-python — do not edit\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class SeedInput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls()\n"
        "    def to_dict(self): return {}\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class SeedOutput:\n"
        "    VERSION: ClassVar[int] = 1\n"
        "    n: int\n"
        "    @classmethod\n"
        "    def from_dict(cls, d): return cls(n=d['n'])\n"
        "    def to_dict(self): return {'n': self.n}\n"
    )
    (seed / "tool.py").write_text(
        "from io_types import SeedInput, SeedOutput\n"
        "\n"
        "def seed(inp: SeedInput) -> SeedOutput:\n"
        "    return SeedOutput(n=7)\n"
    )

    ask = root / "ask"
    ask.mkdir()
    (ask / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object"},
        "output": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
    }))
    (ask / "prompt.md.j2").write_text("Please answer: {{ input }}\n")

    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "seed", "kind": "tool", "version": 1},
            {"id": "ask", "kind": "agent", "version": 1,
             "depends_on_all": ["seed"]},
        ],
    }))
    return root


def _run(capsys, *argv: str) -> tuple[int, str, str]:
    rc = main(list(argv))
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_cli_end_to_end(cli_loom_root: Path, tmp_path: Path, capsys):
    workdir = tmp_path / "run"

    rc, out, _ = _run(capsys, "runtime", "init", str(workdir), "--loom-root", str(cli_loom_root))
    assert rc == 0
    assert out.strip() == str(workdir)
    assert (workdir / "plan.yaml").exists()

    # First `runtime next`: the tool ('seed') runs internally; agent ('ask')
    # surfaces in the ready batch.
    rc, out, _ = _run(capsys, "runtime", "next", str(workdir))
    assert rc == 0
    doc = _parse_next(out)
    assert doc["done"] is False
    assert len(doc["ready"]) == 1
    entry = doc["ready"][0]
    assert entry["id"] == "ask"
    assert entry["kind"] == "agent"
    assert Path(entry["prompt_path"]).read_text().startswith("Please answer")
    assert Path(entry["input_path"]).exists()
    assert entry["output_path"].endswith("output.yaml")

    # Simulate the sub-agent writing output.yaml.
    output_add(workdir, "ask", ["answer=hello"])

    rc, out, _ = _run(capsys, "runtime", "complete", str(workdir), "ask")
    assert rc == 0
    assert out.strip() == "ok"

    # Plan is finished.
    rc, out, _ = _run(capsys, "runtime", "next", str(workdir))
    assert rc == 0
    doc = _parse_next(out)
    assert doc == {"done": True, "ready": []}


def test_cli_complete_reports_schema_error(cli_loom_root: Path, tmp_path: Path, capsys):
    workdir = tmp_path / "run"
    _run(capsys, "runtime", "init", str(workdir), "--loom-root", str(cli_loom_root))
    _run(capsys, "runtime", "next", str(workdir))
    # Write an output missing the required 'answer' field.
    (workdir / "tasks" / "02-ask" / "output.yaml").write_text("{}\n")
    from loom.errors import OutputSchemaError
    with pytest.raises(OutputSchemaError):
        main(["runtime", "complete", str(workdir), "ask"])

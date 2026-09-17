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
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
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
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
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


# --- runtime init --force / --set coverage -----------------------------------


@pytest.fixture
def strict_loom_root(tmp_path: Path) -> Path:
    """Single-agent-task loom with a strict entry input schema.

    Used by the `--set` seeding tests: the schema declares typed
    scalar fields, a required field, and a nested-object list so the
    tests can exercise coercion, grammar, and required-field
    enforcement.
    """
    root = tmp_path / "loom_strict"
    root.mkdir()

    entry = root / "greet"
    entry.mkdir()
    (entry / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
                "enabled": {"type": "boolean"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": "string"},
                            "size": {"type": "integer"},
                        },
                    },
                },
            },
            "required": ["name"],
        },
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
    }))
    (entry / "prompt.md.j2").write_text("Hello {{ input.name }}\n")

    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "greet", "kind": "agent", "version": 1},
        ],
    }))
    return root


@pytest.fixture
def mapping_loom_root(tmp_path: Path) -> Path:
    """Single-agent-task loom whose entry task has an ``input:`` mapping.

    The mapping is an empty ``{}`` — enough to make
    ``entry.input_mapping is not None`` (the SeedNotAllowedError
    trigger) without failing the static reference-locality check on
    an entry with no dependencies.
    """
    root = tmp_path / "loom_mapping"
    root.mkdir()

    entry = root / "greet"
    entry.mkdir()
    (entry / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
    }))
    (entry / "prompt.md.j2").write_text("Hi\n")
    (root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "greet", "kind": "agent", "version": 1, "input": {}},
        ],
    }))
    return root


def test_cli_init_force_wipes_existing_workdir(
    cli_loom_root: Path, tmp_path: Path, capsys
):
    workdir = tmp_path / "run"
    workdir.mkdir()
    (workdir / "leftover.txt").write_text("stale contents")
    rc, out, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(cli_loom_root), "--force",
    )
    assert rc == 0
    assert out.strip() == str(workdir)
    assert not (workdir / "leftover.txt").exists()
    assert (workdir / "plan.yaml").exists()


def test_cli_init_force_on_missing_workdir_is_no_op(
    cli_loom_root: Path, tmp_path: Path, capsys
):
    workdir = tmp_path / "does_not_exist_yet"
    rc, out, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(cli_loom_root), "--force",
    )
    assert rc == 0
    assert (workdir / "plan.yaml").exists()


def test_cli_init_set_seeds_entry_input(
    strict_loom_root: Path, tmp_path: Path, capsys
):
    workdir = tmp_path / "run"
    rc, _, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(strict_loom_root),
        "--set", "name=Alice",
    )
    assert rc == 0
    input_path = workdir / "tasks" / "01-greet" / "input.yaml"
    assert input_path.exists()
    assert yaml.safe_load(input_path.read_text()) == {"name": "Alice"}


def test_cli_init_set_escapes_special_characters(
    strict_loom_root: Path, tmp_path: Path, capsys
):
    workdir = tmp_path / "run"
    tricky = 'quote " backslash \\ newline\nhere'
    rc, _, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(strict_loom_root),
        "--set", f"name={tricky}",
    )
    assert rc == 0
    input_path = workdir / "tasks" / "01-greet" / "input.yaml"
    assert yaml.safe_load(input_path.read_text()) == {"name": tricky}


def test_cli_init_set_rejects_extra_field(
    strict_loom_root: Path, tmp_path: Path, capsys
):
    workdir = tmp_path / "run"
    rc, _, err = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(strict_loom_root),
        "--set", "name=Alice",
        "--set", "not_a_field=x",
    )
    assert rc == 1
    input_path = workdir / "tasks" / "01-greet" / "input.yaml"
    assert not input_path.exists()
    assert "not_a_field" in err or "additionalProperties" in err.lower()


def test_cli_init_set_rejects_missing_required(
    strict_loom_root: Path, tmp_path: Path, capsys
):
    workdir = tmp_path / "run"
    # `count` is declared but `name` (required) is missing.
    rc, _, err = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(strict_loom_root),
        "--set", "count=3",
    )
    assert rc == 1
    input_path = workdir / "tasks" / "01-greet" / "input.yaml"
    assert not input_path.exists()
    assert "name" in err or "required" in err.lower()


def test_cli_init_set_refused_on_mapping_entry(
    mapping_loom_root: Path, tmp_path: Path, capsys
):
    from loom.errors import SeedNotAllowedError

    workdir = tmp_path / "run"
    rc, _, err = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(mapping_loom_root),
        "--set", "anything=x",
    )
    assert rc == 1
    input_path = workdir / "tasks" / "01-greet" / "input.yaml"
    assert not input_path.exists()
    # Cause line from SeedNotAllowedError's docstring surfaces on stderr.
    assert "input" in err and "mapping" in err
    # Sanity: raising the exception directly matches the class contract.
    from loom.cli_run import cmd_init as _cmd_init
    with pytest.raises(SeedNotAllowedError):
        _cmd_init(
            tmp_path / "run_direct",
            mapping_loom_root,
            assignments=["anything=x"],
        )


def test_cli_init_set_supports_output_add_grammar(
    strict_loom_root: Path, tmp_path: Path, capsys
):
    """Dotted / `[]` / `[-1]` assignment grammar mirrors `output add --set`."""
    workdir = tmp_path / "run"
    rc, _, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(strict_loom_root),
        "--set", "name=Alice",
        "--set", "items[].label=first",
        "--set", "items[-1].size=3",
        "--set", "items[].label=second",
        "--set", "items[-1].size=4",
    )
    assert rc == 0
    doc = yaml.safe_load(
        (workdir / "tasks" / "01-greet" / "input.yaml").read_text()
    )
    assert doc == {
        "name": "Alice",
        "items": [
            {"label": "first", "size": 3},
            {"label": "second", "size": 4},
        ],
    }


def test_cli_init_set_coerces_scalars(
    strict_loom_root: Path, tmp_path: Path, capsys
):
    """`_coerce` (bool/int/float) still applies — parity with `output add`."""
    workdir = tmp_path / "run"
    rc, _, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(strict_loom_root),
        "--set", "name=Alice",
        "--set", "count=3",
        "--set", "enabled=true",
    )
    assert rc == 0
    doc = yaml.safe_load(
        (workdir / "tasks" / "01-greet" / "input.yaml").read_text()
    )
    assert doc == {"name": "Alice", "count": 3, "enabled": True}

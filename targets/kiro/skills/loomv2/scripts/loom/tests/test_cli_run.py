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


# --- runtime init auto-workdir / wipe / --set coverage -----------------------


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


def test_cli_init_wipes_existing_explicit_workdir(
    cli_loom_root: Path, tmp_path: Path, capsys
):
    """Explicit-workdir form wipes-and-recreates unconditionally, no flag."""
    workdir = tmp_path / "run"
    workdir.mkdir()
    (workdir / "leftover.txt").write_text("stale contents")
    rc, out, _ = _run(
        capsys, "runtime", "init", str(workdir),
        "--loom-root", str(cli_loom_root),
    )
    assert rc == 0
    assert out.strip() == str(workdir)
    assert not (workdir / "leftover.txt").exists()
    assert (workdir / "plan.yaml").exists()


def test_cli_init_force_flag_rejected(
    cli_loom_root: Path, tmp_path: Path, capsys
):
    """--force is no longer a recognised flag; argparse rejects it."""
    workdir = tmp_path / "run"
    with pytest.raises(SystemExit) as excinfo:
        main([
            "runtime", "init", str(workdir),
            "--loom-root", str(cli_loom_root), "--force",
        ])
    assert excinfo.value.code != 0
    err = capsys.readouterr().err
    assert "--force" in err or "unrecognized" in err.lower()


def test_cli_init_auto_workdir_creates_tmp_path(
    cli_loom_root: Path, capsys
):
    """Omitting the workdir positional creates /tmp/<skill>/<12-hex>/."""
    import shutil

    rc, out, _ = _run(
        capsys, "runtime", "init",
        "--loom-root", str(cli_loom_root),
    )
    assert rc == 0
    printed = out.strip()
    auto_path = Path(printed)
    try:
        assert auto_path.exists()
        assert auto_path.parent == Path("/tmp") / cli_loom_root.parent.name
        assert len(auto_path.name) == 12
        assert all(c in "0123456789abcdef" for c in auto_path.name)
        assert (auto_path / "plan.yaml").exists()
    finally:
        if auto_path.exists():
            shutil.rmtree(auto_path)


def test_cli_init_auto_workdir_skill_name_from_loom_dir(
    tmp_path: Path, capsys
):
    """loom_root basename == 'loom' -> parent dir name is the skill."""
    import shutil

    skill_dir = tmp_path / "my-skill-alpha"
    skill_dir.mkdir()
    loom_root = skill_dir / "loom"
    _build_minimal_loom(loom_root)

    rc, out, _ = _run(
        capsys, "runtime", "init", "--loom-root", str(loom_root),
    )
    assert rc == 0
    auto_path = Path(out.strip())
    try:
        assert auto_path.parent == Path("/tmp") / "my-skill-alpha"
    finally:
        if auto_path.exists():
            shutil.rmtree(auto_path)


def test_cli_init_auto_workdir_skill_name_from_root_basename(
    tmp_path: Path, capsys
):
    """loom_root basename != 'loom' -> that basename is the skill."""
    import shutil

    loom_root = tmp_path / "hello-graph"
    _build_minimal_loom(loom_root)

    rc, out, _ = _run(
        capsys, "runtime", "init", "--loom-root", str(loom_root),
    )
    assert rc == 0
    auto_path = Path(out.strip())
    try:
        assert auto_path.parent == Path("/tmp") / "hello-graph"
    finally:
        if auto_path.exists():
            shutil.rmtree(auto_path)


def test_cli_init_auto_workdir_wipes_collision(
    cli_loom_root: Path, monkeypatch, capsys
):
    """A pre-existing auto path is wiped, not preserved."""
    import shutil
    import uuid as _uuid

    fixed_hex = "abcdef012345"

    class _FixedUUID:
        hex = fixed_hex + "0" * 20  # matches uuid4().hex layout (32 chars)

    monkeypatch.setattr(_uuid, "uuid4", lambda: _FixedUUID())

    skill_name = cli_loom_root.parent.name
    collision = Path("/tmp") / skill_name / fixed_hex
    collision.mkdir(parents=True, exist_ok=True)
    (collision / "stale.txt").write_text("old contents")

    try:
        rc, out, _ = _run(
            capsys, "runtime", "init", "--loom-root", str(cli_loom_root),
        )
        assert rc == 0
        assert out.strip() == str(collision)
        assert not (collision / "stale.txt").exists()
        assert (collision / "plan.yaml").exists()
    finally:
        if collision.exists():
            shutil.rmtree(collision)


def test_cli_init_auto_workdir_cleans_up_on_plan_failure(
    tmp_path: Path, monkeypatch, capsys
):
    """Auto path is deleted when static validation fails."""
    import uuid as _uuid

    fixed_hex = "cafebabe0000"

    class _FixedUUID:
        hex = fixed_hex + "0" * 20

    monkeypatch.setattr(_uuid, "uuid4", lambda: _FixedUUID())

    # A loom_root whose graph.yaml has multiple entries -> MultipleEntriesError
    # from validate_single_entry_exit; init aborts post-mkdir.
    bad_root = tmp_path / "bad-graph"
    bad_root.mkdir()
    for name in ("a", "b"):
        t = bad_root / name
        t.mkdir()
        (t / "io.yaml").write_text(yaml.safe_dump({
            "version": 1,
            "input": {"type": "object", "additionalProperties": False},
            "output": {
                "type": "object", "additionalProperties": False,
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
            },
        }))
        (t / "prompt.md.j2").write_text("hi\n")
    (bad_root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "a", "kind": "agent", "version": 1},
            {"id": "b", "kind": "agent", "version": 1},
        ],
    }))

    auto_path = Path("/tmp") / "bad-graph" / fixed_hex
    if auto_path.exists():
        import shutil
        shutil.rmtree(auto_path)

    rc, _, _ = _run(
        capsys, "runtime", "init", "--loom-root", str(bad_root),
    )
    assert rc == 1
    assert not auto_path.exists()


def test_cli_init_auto_workdir_cleans_up_on_seed_not_allowed(
    mapping_loom_root: Path, monkeypatch, capsys
):
    """Auto path is deleted when --set hits a mapping-bearing entry."""
    import uuid as _uuid

    fixed_hex = "deadbeef1234"

    class _FixedUUID:
        hex = fixed_hex + "0" * 20

    monkeypatch.setattr(_uuid, "uuid4", lambda: _FixedUUID())

    skill_name = mapping_loom_root.name  # basename != 'loom'
    auto_path = Path("/tmp") / skill_name / fixed_hex
    if auto_path.exists():
        import shutil
        shutil.rmtree(auto_path)

    rc, _, err = _run(
        capsys, "runtime", "init",
        "--loom-root", str(mapping_loom_root),
        "--set", "anything=x",
    )
    assert rc == 1
    assert not auto_path.exists()
    assert "input" in err and "mapping" in err


def _build_minimal_loom(loom_root: Path) -> None:
    """Write a one-agent-task loom rooted at ``loom_root`` for auto tests."""
    loom_root.mkdir(parents=True)
    task = loom_root / "greet"
    task.mkdir()
    (task / "io.yaml").write_text(yaml.safe_dump({
        "version": 1,
        "input": {"type": "object", "additionalProperties": False},
        "output": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"greeting": {"type": "string"}},
            "required": ["greeting"],
        },
    }))
    (task / "prompt.md.j2").write_text("Hi\n")
    (loom_root / "graph.yaml").write_text(yaml.safe_dump({
        "tasks": [
            {"id": "greet", "kind": "agent", "version": 1},
        ],
    }))


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

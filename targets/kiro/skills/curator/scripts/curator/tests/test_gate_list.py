"""Tests for ``curator.runtime.cli_gate_list``.

Verifies the TSV contract the gate driver protocol depends on:

- report line first, manifest entries (in manifest order) next,
  synthesis pages (sorted) last
- ``manifest-create`` has 2 fields (kind, replica path); paths
  with spaces and apostrophes survive intact
- ``manifest-modify`` has 3 fields (kind, vault path, replica path)
- ``synthesis-modify`` is emitted when an existing vault page lives
  at the same synthesis path; ``synthesis-create`` otherwise
- Missing manifest entries emit a stderr warning and are skipped
- A missing replica directory exits non-zero
"""
from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from curator import runtime
from curator.vault import config, pages


# ── fixtures ────────────────────────────────────────────


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    """Isolated tmp vault, monkeypatched into vault.config + .pages."""
    vault = tmp_path / "vault"
    for sub in ("12 KEYWORDS", "13 PEOPLE", "14 MODELS",
                "21 WIKI"):
        (vault / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "VAULT_ROOT", vault)
    monkeypatch.setattr(pages,  "VAULT_ROOT", vault)
    return vault


@pytest.fixture
def replica(tmp_path):
    """Empty workdir + vault-replica subtree."""
    wd = tmp_path / "wd"
    rr = wd / "vault-replica"
    rr.mkdir(parents=True)
    return wd, rr


def _write_manifest(rr: Path, entries: list[dict]) -> None:
    (rr / "manifest.yaml").write_text(
        yaml.safe_dump({"entries": entries, "source_basename": "x",
                        "built_at": "1970-01-01T00:00:00Z"}),
        encoding="utf-8",
    )


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# stub\n", encoding="utf-8")


def _parse_tsv(captured: str) -> list[list[str]]:
    return [line.split("\t") for line in captured.splitlines() if line]


# ── tests ───────────────────────────────────────────────


def test_emits_report_first(replica, vault_root, capsys):
    wd, rr = replica
    _touch(rr / "_REPORT.md")
    _write_manifest(rr, [])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    assert rows[0] == ["report", str(rr / "_REPORT.md")]


def test_manifest_create_emits_two_fields(replica, vault_root, capsys):
    wd, rr = replica
    _touch(rr / "12 KEYWORDS/Foo.md")
    _write_manifest(rr, [
        {"vault_path": "12 KEYWORDS/Foo.md", "op": "create",
         "kind": "keywords", "name": "Foo"},
    ])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    assert ["manifest-create", str(rr / "12 KEYWORDS/Foo.md")] in rows


def test_manifest_paths_with_spaces_and_apostrophes_survive(
    replica, vault_root, capsys,
):
    wd, rr = replica
    name = "Claude's C Compiler"  # apostrophe + spaces
    rel = f"12 KEYWORDS/{name}.md"
    _touch(rr / rel)
    _write_manifest(rr, [
        {"vault_path": rel, "op": "create",
         "kind": "keywords", "name": name},
    ])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    # Path field is intact — no shell quoting, no truncation
    assert any(r[0] == "manifest-create" and r[1] == str(rr / rel)
               for r in rows)


def test_manifest_modify_emits_three_fields(replica, vault_root, capsys):
    wd, rr = replica
    rel = "12 KEYWORDS/Foo.md"
    _touch(rr / rel)
    _touch(vault_root / rel)  # original exists
    _write_manifest(rr, [
        {"vault_path": rel, "op": "modified",
         "kind": "keywords", "name": "Foo"},
    ])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    assert ["manifest-modify", str(vault_root / rel),
            str(rr / rel)] in rows


def test_synthesis_create_when_vault_lacks_page(
    replica, vault_root, capsys,
):
    wd, rr = replica
    p = rr / "21 WIKI/Hub.md"
    _touch(p)
    _write_manifest(rr, [])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    assert ["synthesis-create", str(p)] in rows


def test_synthesis_modify_when_vault_has_page(
    replica, vault_root, capsys,
):
    wd, rr = replica
    p_replica = rr / "21 WIKI/Hub.md"
    p_vault   = vault_root / "21 WIKI/Hub.md"
    _touch(p_replica)
    _touch(p_vault)
    _write_manifest(rr, [])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    assert ["synthesis-modify", str(p_vault),
            str(p_replica)] in rows


def test_missing_manifest_entry_warned_and_skipped(
    replica, vault_root, capsys,
):
    """Manifest references a file that isn't on disk → stderr warn,
    line skipped. Surfacing this prevents silent editor no-ops."""
    wd, rr = replica
    _write_manifest(rr, [
        {"vault_path": "12 KEYWORDS/missing.md", "op": "create",
         "kind": "keywords", "name": "missing"},
    ])

    runtime.cli_gate_list(str(wd))

    captured = capsys.readouterr()
    rows = _parse_tsv(captured.out)
    assert all(r[0] != "manifest-create" for r in rows)
    assert "missing" in captured.err


def test_emits_in_protocol_order(replica, vault_root, capsys):
    """report → manifest entries (manifest order) → synthesis (sorted)."""
    wd, rr = replica
    _touch(rr / "_REPORT.md")
    _touch(rr / "12 KEYWORDS/B.md")
    _touch(rr / "12 KEYWORDS/A.md")
    _touch(rr / "21 WIKI/Z.md")
    _touch(rr / "21 WIKI/A.md")
    _write_manifest(rr, [
        {"vault_path": "12 KEYWORDS/B.md", "op": "create",
         "kind": "keywords", "name": "B"},
        {"vault_path": "12 KEYWORDS/A.md", "op": "create",
         "kind": "keywords", "name": "A"},
    ])

    runtime.cli_gate_list(str(wd))

    rows = _parse_tsv(capsys.readouterr().out)
    kinds = [r[0] for r in rows]
    assert kinds == [
        "report",
        "manifest-create",  # B (manifest order)
        "manifest-create",  # A
        "synthesis-create", # 21 WIKI/A.md (sorted)
        "synthesis-create", # 21 WIKI/Z.md
    ]
    # Manifest preserves manifest.yaml order (B before A)
    manifest_paths = [r[1] for r in rows if r[0] == "manifest-create"]
    assert manifest_paths == [
        str(rr / "12 KEYWORDS/B.md"),
        str(rr / "12 KEYWORDS/A.md"),
    ]
    # Synthesis is alphabetical (A before Z)
    synth_paths = [r[1] for r in rows if r[0] == "synthesis-create"]
    assert synth_paths == [
        str(rr / "21 WIKI/A.md"),
        str(rr / "21 WIKI/Z.md"),
    ]


def test_missing_replica_dir_exits_nonzero(tmp_path, vault_root):
    wd = tmp_path / "empty"
    wd.mkdir()
    with pytest.raises(typer.Exit) as exc:
        runtime.cli_gate_list(str(wd))
    assert exc.value.exit_code == 1

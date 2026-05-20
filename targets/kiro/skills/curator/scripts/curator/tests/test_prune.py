"""Tests for ``curator.vault.replica.prune_replica``.

Pins the wikilink-driven pruning rules:

- ``op: modified`` entries are always kept (vault may already
  reference them elsewhere).
- ``op: create`` entries are kept iff a synthesis hub wikilinks
  them (body, alias, heading, frontmatter ``sources:``).
- Wikilinks inside fenced code blocks do NOT count.
- Wikilink targets that match neither a surviving entry nor an
  existing vault page are surfaced as orphan_links.
- The replica file is deleted from disk when an entry is pruned.
- The manifest is rewritten to drop pruned entries.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from curator.vault import config, pages, replica


# ── fixtures ────────────────────────────────────────────


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    """Isolated tmp vault — same shape as test_replica's fixture."""
    vault = tmp_path / "vault"
    for sub in ("12 KEYWORDS", "13 PEOPLE", "14 MODELS",
                 "11 QUOTES", "10 SOURCES", "21 SYNTHESIS"):
        (vault / sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config,  "VAULT_ROOT", vault)
    monkeypatch.setattr(pages,   "VAULT_ROOT", vault)
    return vault


@pytest.fixture
def workdir(tmp_path):
    wd = tmp_path / "wd"
    rr = wd / "vault-replica"
    (rr / "12 KEYWORDS").mkdir(parents=True)
    (rr / "13 PEOPLE").mkdir(parents=True)
    (rr / "14 MODELS").mkdir(parents=True)
    (rr / "21 SYNTHESIS").mkdir(parents=True)
    return wd


def _write_manifest(wd: Path, entries: list[dict]) -> None:
    (wd / "vault-replica" / "manifest.yaml").write_text(
        yaml.safe_dump({
            "entries": entries,
            "source_basename": "x",
            "built_at": "1970-01-01T00:00:00Z",
        }, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _write_replica(wd: Path, vault_path: str, body: str = "stub\n") -> Path:
    p = wd / "vault-replica" / vault_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _write_synthesis(wd: Path, name: str, body: str) -> Path:
    p = wd / "vault-replica" / "21 SYNTHESIS" / name
    p.write_text(body, encoding="utf-8")
    return p


# ── tests ───────────────────────────────────────────────


def test_keeps_create_entry_referenced_by_synthesis(vault_root, workdir):
    """A new artifact wikilinked from a synthesis hub stays put."""
    _write_replica(workdir, "12 KEYWORDS/Foo.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Foo.md", "op": "create",
         "kind": "keywords", "name": "Foo"},
    ])
    _write_synthesis(workdir, "Hub.md",
                     "Body links to [[Foo]] for context.\n")

    result = replica.prune_replica(workdir)

    assert [e["name"] for e in result["kept_linked"]] == ["Foo"]
    assert result["pruned"] == []
    # Replica file survives.
    assert (workdir / "vault-replica" / "12 KEYWORDS/Foo.md").exists()
    # Manifest still has Foo.
    m = yaml.safe_load(
        (workdir / "vault-replica" / "manifest.yaml").read_text())
    assert [e["name"] for e in m["entries"]] == ["Foo"]


def test_prunes_create_entry_not_referenced(vault_root, workdir):
    """An unreferenced new artifact is deleted from disk and
    removed from the manifest."""
    _write_replica(workdir, "12 KEYWORDS/Lonely.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Lonely.md", "op": "create",
         "kind": "keywords", "name": "Lonely"},
    ])
    _write_synthesis(workdir, "Hub.md", "No links here.\n")

    result = replica.prune_replica(workdir)

    assert [e["name"] for e in result["pruned"]] == ["Lonely"]
    assert result["kept_linked"] == []
    # File gone.
    assert not (workdir / "vault-replica" /
                 "12 KEYWORDS/Lonely.md").exists()
    # Manifest empty.
    m = yaml.safe_load(
        (workdir / "vault-replica" / "manifest.yaml").read_text())
    assert m["entries"] == []


def test_keeps_modified_entries_regardless_of_links(vault_root, workdir):
    """Modified entries stay even when no synthesis hub links to
    them — the vault page may already be referenced from
    elsewhere in the vault."""
    # Replica file present, vault original present (modified op).
    _write_replica(workdir, "12 KEYWORDS/Existing.md")
    (vault_root / "12 KEYWORDS/Existing.md").write_text("# vault\n")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Existing.md", "op": "modified",
         "kind": "keywords", "name": "Existing"},
    ])
    _write_synthesis(workdir, "Hub.md", "No links.\n")

    result = replica.prune_replica(workdir)

    assert [e["name"] for e in result["kept_modified"]] == ["Existing"]
    assert result["pruned"] == []
    assert (workdir / "vault-replica" /
            "12 KEYWORDS/Existing.md").exists()


def test_wikilink_with_alias_resolved_to_target(vault_root, workdir):
    """``[[Foo|alias]]`` keeps Foo, not alias."""
    _write_replica(workdir, "12 KEYWORDS/Foo.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Foo.md", "op": "create",
         "kind": "keywords", "name": "Foo"},
    ])
    _write_synthesis(workdir, "Hub.md", "Reference [[Foo|see Foo]].\n")

    result = replica.prune_replica(workdir)
    assert [e["name"] for e in result["kept_linked"]] == ["Foo"]


def test_wikilink_with_heading_resolved_to_target(vault_root, workdir):
    """``[[Foo#section]]`` keeps Foo."""
    _write_replica(workdir, "12 KEYWORDS/Foo.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Foo.md", "op": "create",
         "kind": "keywords", "name": "Foo"},
    ])
    _write_synthesis(workdir, "Hub.md", "See [[Foo#background]].\n")

    result = replica.prune_replica(workdir)
    assert [e["name"] for e in result["kept_linked"]] == ["Foo"]


def test_wikilink_inside_code_block_ignored(vault_root, workdir):
    """Wikilinks in fenced code blocks are NOT counted."""
    _write_replica(workdir, "12 KEYWORDS/Foo.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Foo.md", "op": "create",
         "kind": "keywords", "name": "Foo"},
    ])
    _write_synthesis(workdir, "Hub.md",
                     "Plain text.\n\n```python\n# [[Foo]] in code\n```\n")

    result = replica.prune_replica(workdir)
    assert [e["name"] for e in result["pruned"]] == ["Foo"]


def test_frontmatter_sources_count_as_links(vault_root, workdir):
    """Frontmatter ``sources:`` entries count as wikilink references."""
    _write_replica(workdir, "12 KEYWORDS/Bar.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Bar.md", "op": "create",
         "kind": "keywords", "name": "Bar"},
    ])
    body = (
        "---\n"
        "type: synthesis\n"
        "sources:\n"
        "  - '[[Bar]]'\n"
        "---\n\n"
        "Body has no link.\n"
    )
    _write_synthesis(workdir, "Hub.md", body)

    result = replica.prune_replica(workdir)
    assert [e["name"] for e in result["kept_linked"]] == ["Bar"]


def test_orphan_link_surfaced(vault_root, workdir):
    """Synthesis hub wikilinks a name that is neither a
    surviving manifest entry nor an existing vault page →
    orphan_links contains the target."""
    _write_manifest(workdir, [])
    _write_synthesis(workdir, "Hub.md", "Mentions [[Phantom]].\n")

    result = replica.prune_replica(workdir)
    assert "Phantom" in result["orphan_links"]


def test_existing_vault_page_not_orphan(vault_root, workdir):
    """A wikilink target that already lives in the vault is NOT
    flagged as orphan."""
    (vault_root / "12 KEYWORDS/Known.md").write_text("# vault\n")
    _write_manifest(workdir, [])
    _write_synthesis(workdir, "Hub.md", "Mentions [[Known]].\n")

    result = replica.prune_replica(workdir)
    assert "Known" not in result["orphan_links"]


def test_path_style_wikilink_resolves_to_vault_page(
    vault_root, workdir,
):
    """Path-style wikilinks like ``[[10 SOURCES/Articles/Foo]]``
    resolve to the exact vault path. The slash MUST NOT be
    slug-mangled."""
    (vault_root / "10 SOURCES/Articles").mkdir(parents=True)
    (vault_root / "10 SOURCES/Articles/Some Article.md").write_text(
        "# vault\n")
    _write_manifest(workdir, [])
    _write_synthesis(workdir, "Hub.md",
                     "See [[10 SOURCES/Articles/Some Article]].\n")

    result = replica.prune_replica(workdir)
    assert "10 SOURCES/Articles/Some Article" not in result[
        "orphan_links"]


def test_path_style_wikilink_to_missing_page_is_orphan(
    vault_root, workdir,
):
    """Path-style wikilink to a path that does NOT exist in the
    vault IS surfaced as orphan."""
    (vault_root / "10 SOURCES/Articles").mkdir(parents=True)
    _write_manifest(workdir, [])
    _write_synthesis(workdir, "Hub.md",
                     "See [[10 SOURCES/Articles/Phantom]].\n")

    result = replica.prune_replica(workdir)
    assert "10 SOURCES/Articles/Phantom" in result["orphan_links"]


def test_plain_name_resolves_recursively_in_sources(
    vault_root, workdir,
):
    """``[[Foo]]`` (plain name) resolves to
    ``10 SOURCES/<kind>/Foo.md`` when present in any source
    subfolder. ``10 SOURCES/`` is nested one level by kind
    (Articles, Books, Papers, Videos) and the orphan check must
    recurse one level."""
    (vault_root / "10 SOURCES/Books").mkdir(parents=True)
    (vault_root / "10 SOURCES/Books/Buried Source.md").write_text(
        "# vault\n")
    _write_manifest(workdir, [])
    _write_synthesis(workdir, "Hub.md",
                     "Reference [[Buried Source]].\n")

    result = replica.prune_replica(workdir)
    assert "Buried Source" not in result["orphan_links"]


def test_normalization_collapses_whitespace_and_case(vault_root, workdir):
    """Wikilink target normalized identically to manifest name."""
    _write_replica(workdir, "12 KEYWORDS/Foo Bar.md")
    _write_manifest(workdir, [
        {"vault_path": "12 KEYWORDS/Foo Bar.md", "op": "create",
         "kind": "keywords", "name": "Foo Bar"},
    ])
    _write_synthesis(workdir, "Hub.md", "Reference [[foo  bar]].\n")

    result = replica.prune_replica(workdir)
    assert [e["name"] for e in result["kept_linked"]] == ["Foo Bar"]


def test_missing_replica_dir_raises(vault_root, tmp_path):
    """Calling prune on a workdir without a replica is a hard
    error."""
    wd = tmp_path / "no-replica"
    wd.mkdir()
    with pytest.raises(FileNotFoundError):
        replica.prune_replica(wd)


def test_missing_manifest_raises(vault_root, workdir):
    """Replica without manifest.yaml is a hard error."""
    with pytest.raises(FileNotFoundError):
        replica.prune_replica(workdir)

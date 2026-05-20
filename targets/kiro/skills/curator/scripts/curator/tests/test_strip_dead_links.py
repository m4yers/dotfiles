"""Tests for ``curator.vault.replica.strip_dead_links``.

Pins the post-gate dead-link cleanup contract:

- A wikilink target that resolves (replica file present OR vault
  page present) is kept verbatim.
- A dead ``[[Target]]`` is rewritten to ``Target``.
- A dead ``[[Target|Alias]]`` is rewritten to ``Alias``.
- A dead ``[[Target#anchor]]`` drops the anchor → ``Target``.
- Intra-page links (``[[#section]]``) are kept verbatim.
- Wikilinks inside fenced code blocks are NOT rewritten.
- Frontmatter is preserved byte-for-byte.
- Only files under ``21 WIKI/`` are touched — atomic pages are
  leaves and are skipped.
- Replica files the user deleted at the gate count as dead.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from curator.vault import config, pages, replica


# ── fixtures ────────────────────────────────────────────


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    """Isolated tmp vault — same shape as test_prune."""
    vault = tmp_path / "vault"
    for sub in ("12 KEYWORDS", "13 PEOPLE", "14 MODELS",
                 "11 QUOTES", "10 SOURCES", "21 WIKI"):
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
    (rr / "21 WIKI").mkdir(parents=True)
    return wd


def _write_replica(wd: Path, vault_path: str, body: str = "stub\n") -> Path:
    p = wd / "vault-replica" / vault_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _write_synthesis(wd: Path, name: str, body: str) -> Path:
    p = wd / "vault-replica" / "21 WIKI" / name
    p.write_text(body, encoding="utf-8")
    return p


# ── core rewrite rules ──────────────────────────────────


def test_rewrites_dead_bare_link_to_plain_target(vault_root, workdir):
    """``[[Phantom]]`` with no replica or vault match → ``Phantom``."""
    _write_synthesis(workdir, "Hub.md", "See [[Phantom]] for more.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 1
    assert result["kept_total"] == 0
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "See Phantom for more.\n"


def test_rewrites_dead_aliased_link_to_alias(vault_root, workdir):
    """``[[Phantom|see Phantom]]`` → ``see Phantom``."""
    _write_synthesis(workdir, "Hub.md",
                     "Reference [[Phantom|see Phantom]] here.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "Reference see Phantom here.\n"


def test_rewrites_dead_link_with_heading_drops_anchor(
    vault_root, workdir,
):
    """``[[Phantom#section]]`` → ``Phantom``."""
    _write_synthesis(workdir, "Hub.md", "See [[Phantom#section]].\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "See Phantom.\n"


def test_keeps_link_when_replica_file_exists(vault_root, workdir):
    """``[[Foo]]`` with ``vault-replica/12 KEYWORDS/Foo.md`` present."""
    _write_replica(workdir, "12 KEYWORDS/Foo.md")
    _write_synthesis(workdir, "Hub.md", "Reference [[Foo]] here.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 0
    assert result["kept_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "Reference [[Foo]] here.\n"


def test_keeps_link_when_vault_page_exists(vault_root, workdir):
    """``[[Known]]`` with vault page present, no replica entry."""
    (vault_root / "12 KEYWORDS/Known.md").write_text("# vault\n")
    _write_synthesis(workdir, "Hub.md", "See [[Known]] please.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 0
    assert result["kept_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "See [[Known]] please.\n"


def test_keeps_intra_page_anchor(vault_root, workdir):
    """``[[#Section]]`` is intra-page and never resolves to a target."""
    _write_synthesis(workdir, "Hub.md", "Jump to [[#Section]] below.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 0
    assert result["kept_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "Jump to [[#Section]] below.\n"


def test_keeps_intra_page_anchor_with_alias(vault_root, workdir):
    """``[[#Section|see below]]`` is also intra-page, alias preserved."""
    _write_synthesis(workdir, "Hub.md",
                     "Jump to [[#Section|see below]].\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 0
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "Jump to [[#Section|see below]].\n"


def test_skips_wikilinks_in_fenced_code_blocks(vault_root, workdir):
    """``[[Phantom]]`` inside a fenced block must NOT be rewritten."""
    body = (
        "Plain [[Phantom]] line.\n"
        "\n"
        "```python\n"
        "# [[Phantom]] inside code stays\n"
        "```\n"
    )
    _write_synthesis(workdir, "Hub.md", body)

    result = replica.strip_dead_links(workdir)

    # One stripped (plain line); the code-block one is untouched.
    assert result["stripped_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert "Plain Phantom line." in text
    assert "[[Phantom]] inside code stays" in text


def test_preserves_frontmatter_byte_for_byte(vault_root, workdir):
    """Frontmatter (including comments and key order) is left
    verbatim — only the body changes."""
    body = (
        "---\n"
        "type: synthesis\n"
        "title: Hub\n"
        "sources:\n"
        "  - '[[Phantom]]'\n"
        "last_updated: 1970-01-01\n"
        "---\n\n"
        "Body links to [[Phantom]].\n"
    )
    _write_synthesis(workdir, "Hub.md", body)

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    # Frontmatter block intact — sources entry still has [[ ]].
    assert "  - '[[Phantom]]'" in text
    # Body wikilink stripped to plain text.
    assert "Body links to Phantom." in text


def test_only_synthesis_hubs_are_modified(vault_root, workdir):
    """Atomic pages under 12/13/14 are leaves — never touched."""
    atomic = _write_replica(workdir, "12 KEYWORDS/Foo.md",
                              "Body has [[Phantom]].\n")
    _write_synthesis(workdir, "Hub.md", "Hub has [[Phantom]].\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 1
    # Atomic page untouched.
    assert atomic.read_text() == "Body has [[Phantom]].\n"
    # Hub rewritten.
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "Hub has Phantom.\n"


def test_cross_hub_links_resolve(vault_root, workdir):
    """Hub A wikilinks Hub B's title — both replica files exist
    so both keep their links."""
    _write_synthesis(workdir, "Hub A.md",
                     "Compare with [[Hub B]] for context.\n")
    _write_synthesis(workdir, "Hub B.md",
                     "See [[Hub A]] for the dual view.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 0
    assert result["kept_total"] == 2


def test_user_deleted_replica_file_breaks_links(vault_root, workdir):
    """A manifest-tracked atomic the user deleted at the gate is
    treated as dead — references in synthesis hubs are rewritten."""
    # Originally created, then user deleted at gate (no file on
    # disk, manifest entry irrelevant for this step).
    _write_synthesis(workdir, "Hub.md",
                     "See [[Deleted Item]] for details.\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "See Deleted Item for details.\n"


def test_multiple_links_per_file_partial_strip(vault_root, workdir):
    """Mixed alive/dead links: only dead ones are rewritten."""
    _write_replica(workdir, "12 KEYWORDS/Alive.md")
    _write_synthesis(workdir, "Hub.md",
                     "See [[Alive]] and [[Phantom|p]] and [[Other]].\n")

    result = replica.strip_dead_links(workdir)

    assert result["stripped_total"] == 2
    assert result["kept_total"] == 1
    text = (workdir / "vault-replica" / "21 WIKI" / "Hub.md").read_text()
    assert text == "See [[Alive]] and p and Other.\n"


def test_no_synthesis_dir_is_noop(vault_root, tmp_path):
    """Workdir whose replica has no 21 WIKI/ folder yields zero
    edits without raising."""
    wd = tmp_path / "wd"
    (wd / "vault-replica").mkdir(parents=True)

    result = replica.strip_dead_links(wd)

    assert result == {
        "files_edited":   [],
        "stripped_total": 0,
        "kept_total":     0,
    }


def test_missing_replica_dir_raises(vault_root, tmp_path):
    """Running on a workdir without a replica is a hard error."""
    wd = tmp_path / "no-replica"
    wd.mkdir()
    with pytest.raises(FileNotFoundError):
        replica.strip_dead_links(wd)


def test_files_with_no_dead_links_left_alone(vault_root, workdir):
    """A hub with only resolved links is not edited (no write,
    no entry in files_edited)."""
    _write_replica(workdir, "12 KEYWORDS/Alive.md")
    p = _write_synthesis(workdir, "Hub.md",
                          "All links resolve: [[Alive]].\n")
    mtime_before = p.stat().st_mtime_ns

    result = replica.strip_dead_links(workdir)

    assert result["files_edited"] == []
    assert result["kept_total"] == 1
    # File untouched on disk.
    assert p.stat().st_mtime_ns == mtime_before


def test_files_edited_carries_per_file_stripped_list(
    vault_root, workdir,
):
    """``files_edited`` reports which targets were rewritten."""
    _write_synthesis(workdir, "Hub.md",
                     "Mentions [[Phantom]] and [[Other|o]].\n")

    result = replica.strip_dead_links(workdir)

    assert len(result["files_edited"]) == 1
    edited = result["files_edited"][0]
    assert edited["path"].endswith("21 WIKI/Hub.md")
    targets = [s["target"] for s in edited["stripped"]]
    replacements = [s["replacement"] for s in edited["stripped"]]
    assert targets == ["Phantom", "Other|o"]
    assert replacements == ["Phantom", "o"]

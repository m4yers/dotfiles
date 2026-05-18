"""Tests for ``curator.vault.replica`` — build + apply.

The build step has two branches (Branch 1: page exists in vault →
copy + merge; Branch 2: doesn't exist → fresh page). The apply
step has three outcomes per file (applied, user-deleted, untracked).
Each test pins one of those behaviours with a synthetic tmp vault.

A ``vault_root`` fixture replaces ``VAULT_ROOT`` everywhere it was
captured at import time so tests don't touch the real Obsidian
vault.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from curator.vault import config, pages, replica
from curator.vault.pages import serialize


# ── fixtures ────────────────────────────────────────────


@pytest.fixture
def vault_root(tmp_path, monkeypatch):
    """Isolated tmp vault. Monkeypatches every module that
    captured ``VAULT_ROOT`` at import time so abs_path resolves
    against the tmp dir, not the real Obsidian vault."""
    vault = tmp_path / "vault"
    vault.mkdir()
    # Pre-create every writable folder so save() can land files.
    for sub in ("12 KEYWORDS", "13 PEOPLE", "14 MODELS",
                 "21 SYNTHESIS",
                 "10 SOURCES/Articles", "10 SOURCES/Papers",
                 "10 SOURCES/Books", "10 SOURCES/Videos"):
        (vault / sub).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(config, "VAULT_ROOT", vault)
    monkeypatch.setattr(pages,  "VAULT_ROOT", vault)
    return vault


@pytest.fixture
def workdir(tmp_path):
    """Fresh workdir for each test."""
    wd = tmp_path / "wd"
    wd.mkdir()
    return wd


# ── build_replica — Branch 2 (fresh) ────────────────────


def test_build_creates_fresh_page_when_vault_lacks_target(
    vault_root, workdir,
):
    """When the target vault path does not exist, build_replica
    writes a fresh page into the replica with op=create and
    type-correct frontmatter (no source tracking)."""
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Eventual Consistency",
                 "definition": "Convergent state across replicas.",
                 "definition_source": "agent",
                 "source_quote": "Replicas converge over time."},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }

    result = replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {},
                                     None, "dynamodb-paper")

    # Manifest entry recorded as create.
    entries = result["entries"]
    assert len(entries) == 1
    assert entries[0]["op"]   == "create"
    assert entries[0]["kind"] == "keywords"
    assert entries[0]["vault_path"] == \
        "12 KEYWORDS/Eventual Consistency.md"
    # File lands under the replica at the vault path.
    replica_file = (workdir / "vault-replica" /
                     "12 KEYWORDS" / "Eventual Consistency.md")
    assert replica_file.exists()
    text = replica_file.read_text()
    # Content from the template — title, definition only.
    assert "type: keyword" in text
    assert "title: \"Eventual Consistency\"" in text
    assert "Convergent state across replicas" in text
    # Source-quote rendering removed — the template no longer
    # carries any source-attribution content.
    assert "Replicas converge over time" not in text
    assert "sources:" not in text
    assert "## Source:" not in text
    assert "— from [[" not in text


# ── build_replica — Branch 1 (modified) ─────────────────


def test_build_copies_and_modifies_existing_vault_page(
    vault_root, workdir,
):
    """When the target vault path already exists, build_replica
    overwrites the replica with a freshly-rendered page from the
    new source's content. The op is still recorded as
    ``modified`` so the gate can show a diff against the vault
    original.
    """
    # Pre-populate the vault with an existing keyword page.
    existing_path = vault_root / "12 KEYWORDS" / "Eventual Consistency.md"
    existing_path.write_text(serialize(
        {"type": "keyword"},
        "# Eventual Consistency\n\nAn older definition.\n",
    ))

    composed = {
        "extractions": {
            "keywords": [
                {"name": "Eventual Consistency",
                 "definition": "A new perspective from the new source.",
                 "definition_source": "source",
                 "source_quote": "New paper says..."},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }

    result = replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {},
                                     None, "kleppmann-book")

    entries = result["entries"]
    assert len(entries) == 1
    assert entries[0]["op"] == "modified"
    assert entries[0]["original_path"] == str(existing_path)

    # Replica file is the freshly-rendered page — old content is
    # NOT preserved (build-replica overwrites; the gate's diff
    # view shows the change).
    replica_file = (workdir / "vault-replica" /
                     "12 KEYWORDS" / "Eventual Consistency.md")
    text = replica_file.read_text()
    assert "A new perspective from the new source" in text
    assert "An older definition" not in text   # old content gone
    assert "## Source:" not in text             # no source section
    assert "New paper says" not in text         # no source_quote


# ── build_replica — vault_match alias matching ──────────


def test_build_uses_vault_match_for_alias_lookup(
    vault_root, workdir,
):
    """When vault_match supplies a hit by alias (different
    canonical stem from the item name), build-replica routes the
    output to the matched path with op=modified. The replica
    file is the freshly-rendered page — old content is
    overwritten; the gate's diff view shows the change."""
    # Pre-populate the vault with a page whose stem is "EC.md"
    # but whose frontmatter declares the alias "Eventual
    # Consistency".
    existing_path = vault_root / "12 KEYWORDS" / "EC.md"
    existing_path.write_text(
        "---\ntype: keyword\n"
        "aliases:\n  - Eventual Consistency\n---\n\n"
        "# EC\n\nExisting content.\n",
    )

    composed = {
        "extractions": {
            "keywords": [
                {"name": "Eventual Consistency",
                 "definition": "Convergent state.",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact",
                         "folder": "12 KEYWORDS"},
        },
    }
    # vault_match output as build-replica would receive it.
    vault_matches = {
        "keywords": [
            {"name": "Eventual Consistency",
             "match": "12 KEYWORDS/EC.md"},
        ],
    }

    result = replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, vault_matches,
                                     "new-source")

    entries = result["entries"]
    assert len(entries) == 1
    assert entries[0]["op"]         == "modified"
    assert entries[0]["vault_path"] == "12 KEYWORDS/EC.md"
    # Replica file is at the matched path (EC.md, not the
    # canonical eventual-consistency.md slug). Content is the
    # fresh render, not the old vault content.
    replica_file = (workdir / "vault-replica" /
                     "12 KEYWORDS" / "EC.md")
    assert replica_file.exists()
    text = replica_file.read_text()
    assert "Convergent state." in text
    # Title comes from the item name, not the existing stem.
    assert 'title: "Eventual Consistency"' in text
    # Old vault content is gone (build-replica overwrites).
    assert "Existing content." not in text


# ── manifest ───────────────────────────────────────────


def test_build_writes_manifest_listing_every_replica_file(
    vault_root, workdir,
):
    """Every entry returned by build_replica is also recorded in
    ``manifest.yaml`` at the replica root."""
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Alpha", "definition": "first letter",
                 "definition_source": "agent"},
                {"name": "Beta",  "definition": "second letter",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }
    replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, None, "src")

    manifest_path = (workdir / "vault-replica" / "manifest.yaml")
    assert manifest_path.exists()
    manifest = yaml.safe_load(manifest_path.read_text())
    paths = sorted(e["vault_path"] for e in manifest["entries"])
    assert paths == ["12 KEYWORDS/Alpha.md", "12 KEYWORDS/Beta.md"]


# ── apply_replica ──────────────────────────────────────


def test_apply_writes_every_tracked_file_to_vault(
    vault_root, workdir,
):
    """Build produces a replica; apply walks it and writes each
    file to the vault via pages.save."""
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Alpha",
                 "definition": "first letter",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }
    replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, None, "src")

    result = replica.apply_replica(workdir)
    assert result["ok"] is True
    assert len(result["results"]) == 1
    r = result["results"][0]
    assert r["ok"] is True
    assert r["op"] == "create"
    assert r["vault_path"] == "12 KEYWORDS/Alpha.md"
    # And the file actually lands in the vault.
    assert (vault_root / "12 KEYWORDS" / "Alpha.md").exists()


def test_apply_skips_user_deleted_files(vault_root, workdir):
    """If the user deletes a replica file between build and apply,
    apply_replica records ``skipped: True, reason: user_deleted``
    and does NOT write to the vault."""
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Keep",   "definition": "keep me",
                 "definition_source": "agent"},
                {"name": "Reject", "definition": "user removed",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }
    replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, None, "src")

    # User deletes the rejected file.
    rejected = (workdir / "vault-replica" /
                 "12 KEYWORDS" / "Reject.md")
    assert rejected.exists()
    rejected.unlink()

    result = replica.apply_replica(workdir)

    # Apply considers the deletion a deliberate rejection: ok still
    # true overall, the deleted file is recorded as skipped.
    assert result["ok"] is True
    by_path = {r["vault_path"]: r for r in result["results"]}
    assert by_path["12 KEYWORDS/Keep.md"]["ok"] is True
    assert by_path["12 KEYWORDS/Reject.md"]["skipped"] is True
    assert by_path["12 KEYWORDS/Reject.md"]["reason"] == "user_deleted"
    # Vault has only the kept file.
    assert (vault_root / "12 KEYWORDS" / "Keep.md").exists()
    assert not (vault_root / "12 KEYWORDS" / "Reject.md").exists()


def test_apply_flags_untracked_replica_files_as_errors(
    vault_root, workdir,
):
    """If a file appears in the replica but isn't in the manifest
    (e.g. the user dropped a new file there manually), apply
    flags it as an error rather than silently writing it."""
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Tracked", "definition": "tracked",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }
    replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, None, "src")

    # User adds an untracked file.
    untracked = (workdir / "vault-replica" /
                  "12 KEYWORDS" / "Smuggled.md")
    untracked.write_text(serialize(
        {"type": "keyword",
         "sources": ["10 SOURCES/Articles/src"]},
        "# Smuggled\n\nManual addition.\n",
    ))

    result = replica.apply_replica(workdir)

    assert result["ok"] is False
    by_path = {r["vault_path"]: r for r in result["results"]}
    assert by_path["12 KEYWORDS/Tracked.md"]["ok"] is True
    assert by_path["12 KEYWORDS/Smuggled.md"]["ok"] is False
    assert "untracked" in by_path["12 KEYWORDS/Smuggled.md"]["error"]


def test_apply_records_validation_failure_per_path(
    vault_root, workdir, monkeypatch,
):
    """A replica file that fails ``pages.save`` validation (e.g.
    missing required ``type`` frontmatter) is recorded as
    ``ok: False`` without aborting the rest of the batch."""
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Good", "definition": "ok",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
        "synthesis_pages": [],
    }
    replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, None, "src")

    # Corrupt the replica file: strip frontmatter to trigger
    # _ensure_required_frontmatter failure inside apply.
    bad_file = (workdir / "vault-replica" /
                 "12 KEYWORDS" / "Good.md")
    bad_file.write_text("# Good\n\nNo frontmatter here.\n")

    result = replica.apply_replica(workdir)

    assert result["ok"] is False
    r = result["results"][0]
    assert r["ok"] is False
    assert "type" in r["error"]   # missing required field



def test_apply_accepts_untracked_synthesis_pages(
    vault_root, workdir,
):
    """Synthesis pages live under ``21 SYNTHESIS/`` and are
    written directly into the replica by the synthesis agent
    (NOT via the build-replica manifest). Apply-replica should
    pick them up, validate, and save them.

    Untracked files OUTSIDE ``21 SYNTHESIS/`` remain errors.
    """
    composed = {
        "extractions": {
            "keywords": [
                {"name": "Atomic", "definition": "atomic",
                 "definition_source": "agent"},
            ],
        },
        "extraction_destinations": {
            "keywords": {"mode": "artifact", "folder": "12 KEYWORDS"},
        },
    }
    replica.build_replica(workdir, composed.get("extractions") or {}, composed.get("extraction_destinations") or {}, None, "src")

    # Synthesis agent simulates writing a hub page directly.
    syn_dir = workdir / "vault-replica" / "21 SYNTHESIS"
    syn_dir.mkdir(parents=True, exist_ok=True)
    syn_file = syn_dir / "the-hub.md"
    syn_file.write_text(serialize(
        {"type":         "synthesis",
         "title":        "The Hub",
         "sources":      ["10 SOURCES/Articles/src"],
         "last_updated": "2026-05-18"},
        "# The Hub\n\nA short hub overview citing [[Atomic]].\n",
    ))

    # And an untracked file in the WRONG folder — should error.
    bad_file = (workdir / "vault-replica" /
                 "12 KEYWORDS" / "Smuggled.md")
    bad_file.write_text(serialize(
        {"type":         "keyword",
         "sources":      ["10 SOURCES/Articles/src"],
         "last_updated": "2026-05-18"},
        "# Smuggled\n\nManual addition.\n",
    ))

    result = replica.apply_replica(workdir)

    by_path = {r["vault_path"]: r for r in result["results"]}
    # Tracked atomic page applied.
    assert by_path["12 KEYWORDS/Atomic.md"]["ok"] is True
    # Untracked synthesis page accepted (under 21 SYNTHESIS/).
    assert by_path["21 SYNTHESIS/the-hub.md"]["ok"] is True
    assert by_path["21 SYNTHESIS/the-hub.md"]["kind"] == "synthesis"
    assert by_path["21 SYNTHESIS/the-hub.md"]["op"] == "create"
    # Untracked non-synthesis flagged as error.
    assert by_path["12 KEYWORDS/Smuggled.md"]["ok"] is False
    assert "untracked" in by_path["12 KEYWORDS/Smuggled.md"]["error"]
    # And synthesis page actually landed in the vault.
    assert (vault_root / "21 SYNTHESIS" / "the-hub.md").exists()

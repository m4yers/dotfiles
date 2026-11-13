"""Vault configuration constants — paths, scope rules, tunables.

No imports from sibling vault modules. Every other vault module
reads its constants from here so changes to the vault layout (folder
renames, new readonly subtrees) live in one place.
"""
from __future__ import annotations

import os
from pathlib import Path


# ── vault root ──────────────────────────────────────────

_DEFAULT_VAULT_ROOT = "~/Obsidian/MahVault"

# Resolve at import time so abs_path's startswith check is symlink-
# stable. On hosts where /home is a symlink to /local/home, a lazily-
# computed VAULT_ROOT would stay /home/... while a resolved child
# path would be /local/home/..., breaking the escape check.
VAULT_ROOT = Path(
    os.path.expanduser(os.environ.get("VAULT_ROOT",
                                        _DEFAULT_VAULT_ROOT))
).resolve()


# ── folder roles ───────────────────────────────────────

SOURCES_DIR   = "10 SOURCES"
QUOTES_DIR    = "11 QUOTES"
KEYWORDS_DIR  = "12 KEYWORDS"
PEOPLE_DIR    = "13 PEOPLE"
MODELS_DIR    = "14 MODELS"
ZETTEL_DIR    = "20 ZETTELKASTEN"
SYNTHESIS_DIR = "21 WIKI"


# Vault scope — what the agent may create / modify directly.
#
# Zettel-dir is intentionally NOT in WRITABLE_PREFIXES; the vault
# shim admits it only when the orchestrator has verified that
# the user explicitly named a zettel (see ``_is_writable`` in
# pages.py — the gate is procedural, not flag-driven).
WRITABLE_PREFIXES = (
    f"{SOURCES_DIR}/Papers",
    f"{SOURCES_DIR}/Books",
    f"{SOURCES_DIR}/Articles",
    f"{SOURCES_DIR}/Videos",
    QUOTES_DIR,
    KEYWORDS_DIR,
    PEOPLE_DIR,
    MODELS_DIR,
    SYNTHESIS_DIR,
)

# Paths under SOURCES that must remain binary / immutable. The
# matching ``*.assets/`` sibling folders are enforced by path check
# in ``pages._is_writable`` separately.
BINARY_SUFFIXES = (".pdf", ".epub", ".mp3", ".mp4")


# ── kind → folder map ──────────────────────────────────
#
# Canonical top-level folder for each kind of note. Keyed by the
# vocabulary the vault AGENTS.md files and the agent use.
FOLDERS = {
    "sources":  SOURCES_DIR,
    "quotes":   QUOTES_DIR,
    "keywords": KEYWORDS_DIR,
    "people":   PEOPLE_DIR,
    "models":   MODELS_DIR,
    "zettels":  ZETTEL_DIR,
    "wiki":     SYNTHESIS_DIR,
}


# ── defaults for cross-folder search ──────────────────
#
# Folders ``vault search`` scans when the caller does not pass
# ``--folder``. 30/31/60 are personal/private areas the vault does
# not index by default.
DEFAULT_SEARCH_FOLDERS = (
    SOURCES_DIR,
    QUOTES_DIR,
    KEYWORDS_DIR,
    PEOPLE_DIR,
    MODELS_DIR,
    ZETTEL_DIR,
    SYNTHESIS_DIR,
)


# ── obsidian desktop app ───────────────────────────────

OBSIDIAN_CLI = Path(
    "/Applications/Obsidian.app/Contents/MacOS/Obsidian"
)

# Max seconds to wait for an obsidian CLI move/rename/delete, both
# for the CLI call to return and for the result to land on the
# filesystem. 10s covers a cold cache; if obsidian is not running
# the wait will time out and surface a clear error.
OBSIDIAN_OP_TIMEOUT_S = 10

# How often to re-stat the vault during a wait loop.
OBSIDIAN_POLL_INTERVAL_S = 0.25


# ── vault search ───────────────────────────────────────

# Cap on total ``vault search`` hits returned to the orchestrator.
# 200 is a compromise between:
# - a human-readable preview (the orchestrator shows the hit list to
#   the user), which saturates well before 200 lines; and
# - a tight enough ceiling that a catastrophic query (empty string,
#   short common token) cannot flood the shim stdout or stall the
#   orchestrator parsing the YAML envelope.
# When a legitimate search is truncated, the caller should scope it
# with ``--folder`` rather than raise the cap.
VAULT_SEARCH_MAX_RESULTS = 200

# Timeout for the ripgrep subprocess in notes.search. 30s is chosen
# to cover a cold-page-cache scan of a few-thousand-note vault; any
# vault that does not return within 30s indicates either a runaway
# query, a stalled filesystem, or an rg bug — the Python fallback
# takes over on timeout.
VAULT_SEARCH_RG_TIMEOUT_S = 30

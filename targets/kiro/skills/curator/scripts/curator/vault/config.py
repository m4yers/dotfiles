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
    os.path.expanduser(os.environ.get("CURATOR_VAULT_ROOT",
                                       _DEFAULT_VAULT_ROOT))
).resolve()


# ── folder roles (definitive spec for curator scope) ───

SOURCES_DIR   = "10 SOURCES"
QUOTES_DIR    = "11 QUOTES"
KEYWORDS_DIR  = "12 KEYWORDS"
PEOPLE_DIR    = "13 PEOPLE"
MODELS_DIR    = "14 MODELS"
ZETTEL_DIR    = "20 ZETTELKASTEN"
SYNTHESIS_DIR = "21 SYNTHESIS"

# Curator write list. Paths under these prefixes are writable.
WRITABLE_PREFIXES = (
    KEYWORDS_DIR,
    PEOPLE_DIR,
    MODELS_DIR,
    SYNTHESIS_DIR,
    f"{SOURCES_DIR}/Papers",
    f"{SOURCES_DIR}/Books",
    f"{SOURCES_DIR}/Articles",
    f"{SOURCES_DIR}/Videos",
)

# Paths under SOURCES that must remain binary / immutable.
BINARY_SUFFIXES = (".pdf", ".epub", ".mp3", ".mp4")

# Folders the curator never writes to, even if the path is under a
# writable prefix as a subtree (belt-and-braces).
READ_ONLY_DIRS = (QUOTES_DIR, ZETTEL_DIR)

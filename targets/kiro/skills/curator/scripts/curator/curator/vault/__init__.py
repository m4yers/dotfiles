"""Vault package — public re-exports.

External callers — the source handlers and ``__main__`` — only
need a small surface from ``curator.vault``: the CLI ``app`` and
six primitives the source handlers consume directly. Everything
else is internal to the vault package and should be imported from
its sub-module directly.

Sub-module map:

- ``curator.vault.config``    constants: VAULT_ROOT, *_DIR
- ``curator.vault.pages``     low-level CRUD + frontmatter helpers
- ``curator.vault.match``     find_matches / build_match
- ``curator.vault.replica``   build_replica / apply_replica
- ``curator.vault.cli``       typer app + CLI entrypoints
"""
from __future__ import annotations

# Constants used by source handlers.
from curator.vault.config import (
    SOURCES_DIR,
    VAULT_ROOT,
)

# Page helpers used by source handlers.
from curator.vault.pages import (
    abs_path,
    parse,
    serialize,
    slugify_basename,
)

# CLI surface — mounted by curator/__main__.py.
from curator.vault.cli import app


__all__ = [
    "SOURCES_DIR",
    "VAULT_ROOT",
    "abs_path",
    "app",
    "parse",
    "serialize",
    "slugify_basename",
]

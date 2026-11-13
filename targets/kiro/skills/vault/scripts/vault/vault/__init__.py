"""vault: Obsidian vault read/write primitives + source ingestion.

Top-level package exposing path resolution, frontmatter-safe page
read/write, name matching, and a ported source-handler pipeline.
Public re-exports keep the source handlers' imports flat.
"""
from __future__ import annotations

__version__ = "0.1.0"

from vault.config import (
    SOURCES_DIR,
    VAULT_ROOT,
)
from vault.pages import (
    abs_path,
    parse,
    serialize,
    slugify_basename,
)

__all__ = [
    "SOURCES_DIR",
    "VAULT_ROOT",
    "abs_path",
    "parse",
    "serialize",
    "slugify_basename",
]

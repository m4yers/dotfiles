"""Build vault context for sub-agent extractors.

Returns existing names per type so extractors can dedup. Names are
keyed by folder.
"""
from __future__ import annotations

from pathlib import Path

from engine import vault
from engine.config import CONTEXT_FAST_PARSE_LIMIT

TYPE_TO_FOLDER = {
    "keywords":  vault.KEYWORDS_DIR,
    "people":    vault.PEOPLE_DIR,
    "models":    vault.MODELS_DIR,
    "synthesis": vault.SYNTHESIS_DIR,
}


def build_context(types: list[str] | None = None) -> dict:
    """Return {keywords: [...], people: [...], models: [...], synthesis: [...], scope_rules, page_templates}.

    Each list entry: {name, path, size, has_frontmatter}.
    """
    if types is None:
        types = list(TYPE_TO_FOLDER.keys())

    out = {}
    for t in types:
        folder = TYPE_TO_FOLDER.get(t)
        if not folder:
            raise ValueError(f"unknown type: {t}")
        out[t] = _list_folder(folder)

    out["scope_rules"] = {
        "writable_prefixes": list(vault.WRITABLE_PREFIXES),
        "read_only_dirs": list(vault.READ_ONLY_DIRS),
        "binary_suffixes": list(vault.BINARY_SUFFIXES),
    }
    out["vault_root"] = str(vault.VAULT_ROOT)
    return out


def _list_folder(folder: str) -> list[dict]:
    out = []
    for p in vault.list_md(folder):
        size = p.stat().st_size
        try:
            raw = p.read_text(encoding="utf-8") if size < CONTEXT_FAST_PARSE_LIMIT else ""
            fm, _ = vault.try_parse(raw) if raw else ({}, "")
            aliases = fm.get("aliases", []) if isinstance(fm, dict) else []
        except Exception:
            aliases = []
        out.append({
            "name": p.stem,
            "path": vault.rel_path(p),
            "size": size,
            "aliases": aliases or [],
        })
    return sorted(out, key=lambda x: x["name"].lower())

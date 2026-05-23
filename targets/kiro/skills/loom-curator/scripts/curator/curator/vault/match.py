"""Match extracted items against existing vault pages.

Used by the ``vault_match`` tool task in stage 2 to attach
``match_existing`` references to per-kind extractor outputs. Match
is by stem or alias with case-insensitive whitespace-collapsed
comparison.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from curator.vault.config import KEYWORDS_DIR, MODELS_DIR, PEOPLE_DIR
from curator.vault.pages import list_md, rel_path, try_parse


# Maps the kind name used in extractor outputs to the vault folder
# the matcher should search. Topics + summary have no vault folder
# and are emitted as empty lists by ``build_match``.
_KIND_TO_FOLDER = {
    "keywords": KEYWORDS_DIR,
    "people":   PEOPLE_DIR,
    "models":   MODELS_DIR,
}


def _normalize(name: str) -> str:
    """Lowercase + strip + collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", name.lower()).strip()


def _read_frontmatter(p: Path) -> dict:
    """Read just the YAML frontmatter from a markdown file.

    Frontmatter sits at the file head, delimited by ``---`` lines.
    Reading the first 4 KB is enough for any realistic frontmatter
    block; this is much cheaper than reading megabyte source pages.
    """
    try:
        with p.open("rb") as fh:
            head = fh.read(4096).decode("utf-8", errors="replace")
    except OSError:
        return {}
    if not head.startswith("---"):
        return {}
    fm, _ = try_parse(head)
    return fm if isinstance(fm, dict) else {}


def _list_folder(folder: str) -> list[dict]:
    """Per-page metadata records for a single vault folder.

    Each record carries ``name``, ``path``, ``size``, ``aliases``,
    plus any ``origin_url`` / ``published_date`` / ``author`` from
    frontmatter.
    """
    out = []
    for p in list_md(folder):
        size = p.stat().st_size
        fm = _read_frontmatter(p)
        aliases    = fm.get("aliases") or []
        origin_url = fm.get("origin_url")
        published  = fm.get("published_date") or fm.get("date")
        author     = fm.get("author")

        entry = {
            "name":    p.stem,
            "path":    rel_path(p),
            "size":    size,
            "aliases": aliases,
        }
        if origin_url:
            entry["origin_url"] = origin_url
        if published:
            entry["published_date"] = str(published)
        if author:
            entry["author"] = author
        out.append(entry)
    return sorted(out, key=lambda x: x["name"].lower())


def find_matches(items: list[dict], folder: str) -> list[dict]:
    """For each item in ``items`` (each must have ``name``), search
    the given vault folder for an existing page whose stem or
    aliases match. Returns a list of ``{name, match}`` where
    ``match`` is the relative path of the matched page or ``None``.
    """
    candidates = _list_folder(folder)
    by_norm: dict[str, str] = {}
    for c in candidates:
        by_norm[_normalize(c["name"])] = c["path"]
        for alias in c.get("aliases") or []:
            by_norm[_normalize(alias)] = c["path"]

    out: list[dict] = []
    for item in items:
        name = item.get("name", "")
        out.append({
            "name":  name,
            "match": by_norm.get(_normalize(name)),
        })
    return out


def build_match(extractor_outputs: dict[str, str]) -> dict:
    """For each ``(kind, output_path)`` pair, load the extractor
    output and find vault matches for its items. Returns a dict
    keyed by kind, each holding a list of ``{name, match}``."""
    out: dict = {}
    for kind, path in extractor_outputs.items():
        folder = _KIND_TO_FOLDER.get(kind)
        if not folder:
            # Topics + summary have no vault folder; emit empty list.
            out[kind] = []
            continue
        if not Path(path).exists():
            out[kind] = []
            continue
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        items = data.get(kind) if isinstance(data, dict) else None
        out[kind] = find_matches(items or [], folder)
    return out

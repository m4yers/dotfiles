"""Match extracted items against existing vault pages.

Match is by stem or alias with case-insensitive
whitespace-collapsed comparison.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from vault.config import KEYWORDS_DIR, MODELS_DIR, PEOPLE_DIR
from vault.pages import list_md, parse, rel_path
from vault.utils import fail


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
    Reads line by line until the closing delimiter so a long block
    is never truncated, and stops there so megabyte source pages
    are not read whole. Raises ``ValueError`` on malformed YAML or
    an unreadable file; returns ``{}`` when the file has no
    frontmatter.
    """
    lines: list[str] = []
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
            if first.rstrip("\n") != "---":
                return {}
            lines.append(first)
            for line in fh:
                lines.append(line)
                if line.rstrip("\n") == "---":
                    break
            else:
                raise ValueError("frontmatter has no closing ---")
    except OSError as e:
        raise ValueError(f"unreadable: {e}")
    fm, _ = parse("".join(lines))
    return fm


def _list_folder(folder: str) -> tuple[list[dict], list[dict]]:
    """Per-page metadata records for a single vault folder.

    Returns ``(entries, skipped)``. Each entry carries ``name``,
    ``path``, ``size``, ``aliases``, plus any ``origin_url`` /
    ``published_date`` / ``author`` from frontmatter. ``skipped``
    lists ``{path, reason}`` for pages whose frontmatter failed to
    parse; they take part in stem matching but their aliases are
    unknown, so the caller must surface them.
    """
    out = []
    skipped: list[dict] = []
    for p in list_md(folder):
        size = p.stat().st_size
        try:
            fm = _read_frontmatter(p)
        except ValueError as e:
            skipped.append({"path": rel_path(p), "reason": str(e)})
            fm = {}
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
    return sorted(out, key=lambda x: x["name"].lower()), skipped


def find_matches(items: list[dict], folder: str
                 ) -> tuple[list[dict], list[dict]]:
    """For each item in ``items`` (each must have ``name``), search
    the given vault folder for an existing page whose stem or
    aliases match. Returns ``(matches, skipped)``: ``matches`` is a
    list of ``{name, match}`` where ``match`` is the relative path
    of the matched page or ``None``; ``skipped`` is the folder's
    unparseable-frontmatter list from ``_list_folder``.
    """
    candidates, skipped = _list_folder(folder)
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
    return out, skipped


def build_match(extractor_outputs: dict[str, str]) -> dict:
    """For each ``(kind, output_path)`` pair, load the extractor
    output and find vault matches for its items. Returns::

        {
          <kind>:  [{name, match: <vault path or null>}, ...],
          skipped: [{path, reason}, ...],
        }

    ``skipped`` lists pages whose frontmatter could not be parsed;
    their aliases did not take part in matching, so a ``null``
    match may be a false negative when the list is non-empty.

    Each input file must be a YAML mapping shaped
    ``{<kind>: [{name: <str>}, ...]}`` (kind is ``keywords``,
    ``people``, or ``models``). Fails on a missing file, a missing
    kind key, or an item without a ``name``."""
    out: dict = {}
    skipped: list[dict] = []
    for kind, path in extractor_outputs.items():
        folder = _KIND_TO_FOLDER.get(kind)
        if not folder:
            # Topics + summary have no vault folder; emit empty list.
            out[kind] = []
            continue
        if not Path(path).exists():
            fail(f"--{kind} input not found: {path}")
        try:
            data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as e:
            fail(f"--{kind} input unreadable: {path}: {e}")
        if not isinstance(data, dict) or not isinstance(
                data.get(kind), list):
            fail(f"--{kind} input {path} must be a mapping with a "
                 f"'{kind}' list of {{name}} items")
        items = data[kind]
        bad = [i for i, item in enumerate(items)
               if not isinstance(item, dict)
               or not isinstance(item.get("name"), str)
               or not item["name"].strip()]
        if bad:
            fail(f"--{kind} input {path}: items missing 'name' at "
                 f"index {', '.join(map(str, bad))}")
        out[kind], folder_skipped = find_matches(items, folder)
        skipped.extend(folder_skipped)
    out["skipped"] = skipped
    return out

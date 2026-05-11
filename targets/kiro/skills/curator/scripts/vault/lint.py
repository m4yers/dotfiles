"""Lint — vault health scan.

Categories:
- stubs      — 0-byte or minimal pages (uses pages.stubs)
- orphans    — writable pages nothing links to (uses pages.orphans)
- misfiled   — reference-like pages in 20 ZETTELKASTEN/ that belong in 12 KEYWORDS/
- uncited    — writable-folder pages with no sources frontmatter
- stale      — pages with last_updated older than N days

Workdir (``/tmp/curator/*``) staleness is a separate concern
reported by the disk tool (``disk.sh workdir list-stale``).
"""
from __future__ import annotations

import datetime
import re
from pathlib import Path

from vault import pages, vault
from vault.config import PAGE_STALE_DAYS

STALE_DAYS = PAGE_STALE_DAYS
MISFILING_HINTS = (
    # Terms that look like reference/keyword pages when they land in zettelkasten.
    r"^[A-Z0-9][\w\s\-\(\)]*\s*\([A-Z][\w\s\-]*\)\.md$",  # "MOSFET (Metal-...)"
    r"^[A-Z][A-Z0-9][A-Z0-9\-]+\.md$",                    # all-caps acronyms
)


def lint(scope: str = "all") -> dict:
    out = {}
    if scope in ("all", "stubs"):
        out["stubs"] = pages.stubs().get("stubs", [])
    if scope in ("all", "orphans"):
        out["orphans"] = pages.orphans().get("orphans", [])
    if scope in ("all", "misfiled"):
        out["misfiled"] = _misfiled()
    if scope in ("all", "uncited"):
        out["uncited"] = _uncited()
    if scope in ("all", "stale"):
        out["stale"] = _stale()
    return out


def _misfiled() -> list[dict]:
    """Zettelkasten pages whose filename matches reference-like patterns."""
    patterns = [re.compile(p) for p in MISFILING_HINTS]
    candidates = []
    for p in vault.list_md(vault.ZETTEL_DIR):
        name = p.name
        if any(rx.match(name) for rx in patterns):
            candidates.append(
                {
                    "from": vault.rel_path(p),
                    "to": f"{vault.KEYWORDS_DIR}/{p.name}",
                    "reason": "filename matches reference-page pattern",
                }
            )
    return candidates


def _uncited() -> list[dict]:
    out = []
    for folder in (vault.KEYWORDS_DIR, vault.PEOPLE_DIR, vault.MODELS_DIR, vault.SYNTHESIS_DIR):
        for p in vault.list_md(folder):
            try:
                raw = p.read_text(encoding="utf-8")
            except Exception:
                continue
            fm, body = vault.try_parse(raw)
            if fm.get("sources"):
                continue
            # Accept body-citation escape hatch.
            if _has_source_wikilink(body):
                continue
            out.append({"path": vault.rel_path(p)})
    return out


def _stale() -> list[dict]:
    cutoff = datetime.date.today() - datetime.timedelta(days=STALE_DAYS)
    out = []
    for folder in (vault.KEYWORDS_DIR, vault.PEOPLE_DIR, vault.MODELS_DIR, vault.SYNTHESIS_DIR):
        for p in vault.list_md(folder):
            try:
                raw = p.read_text(encoding="utf-8")
            except Exception:
                continue
            fm, _ = vault.try_parse(raw)
            lu = fm.get("last_updated")
            if not lu:
                continue
            try:
                d = datetime.date.fromisoformat(str(lu)[:10])
            except ValueError:
                continue
            if d < cutoff:
                out.append({"path": vault.rel_path(p), "last_updated": str(lu)})
    return out


_LINK_RE = re.compile(r"\[\[([^\]|#]+)")


def _has_source_wikilink(body: str) -> bool:
    for m in _LINK_RE.finditer(body):
        t = m.group(1).strip()
        if t.startswith((vault.SOURCES_DIR, vault.QUOTES_DIR)):
            return True
    return False

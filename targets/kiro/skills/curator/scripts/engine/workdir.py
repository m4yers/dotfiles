"""Workdir management.

Per-ingest scratch dir under /tmp/curator/<date>/<slug>/.
Holds source.md, sub-agent JSON outputs, and approved.json.
Swept at end of ingest or by lint.
"""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from slugify import slugify

from engine.config import SLUG_MAX_LENGTH, WORKDIR_STALE_DAYS

WORKDIR_ROOT = Path("/tmp/curator")
STALE_DAYS = WORKDIR_STALE_DAYS


def today() -> str:
    return datetime.date.today().isoformat()


def create_workdir(basename: str) -> Path:
    """Create /tmp/curator/<date>/<slug>/ with a unique slug.

    If a dir with the desired slug already exists today, append -2, -3, …
    """
    slug_base = slugify(basename, max_length=SLUG_MAX_LENGTH)
    day_dir = WORKDIR_ROOT / today()
    day_dir.mkdir(parents=True, exist_ok=True)
    slug = slug_base
    n = 2
    while (day_dir / slug).exists():
        slug = f"{slug_base}-{n}"
        n += 1
    wd = day_dir / slug
    wd.mkdir(parents=True)
    return wd


def sweep(path: str | None = None, all_stale: bool = False) -> dict:
    """Delete one workdir or all stale ones (older than STALE_DAYS).

    Returns summary JSON.
    """
    removed = []
    if path:
        p = Path(path).resolve()
        if not str(p).startswith(str(WORKDIR_ROOT)):
            raise ValueError(f"path not inside {WORKDIR_ROOT}: {path}")
        if p.exists():
            shutil.rmtree(p)
            removed.append(str(p))
        return {"removed": removed, "ok": True}

    if all_stale:
        if not WORKDIR_ROOT.exists():
            return {"removed": [], "ok": True}
        cutoff = datetime.date.today() - datetime.timedelta(days=STALE_DAYS)
        for day_dir in WORKDIR_ROOT.iterdir():
            if not day_dir.is_dir():
                continue
            try:
                day = datetime.date.fromisoformat(day_dir.name)
            except ValueError:
                continue
            if day <= cutoff:
                shutil.rmtree(day_dir)
                removed.append(str(day_dir))
        return {"removed": removed, "ok": True}

    return {"removed": [], "ok": True, "note": "no path and --all not set"}


def list_stale() -> list[str]:
    """Return stale workdir paths (older than STALE_DAYS), for lint."""
    if not WORKDIR_ROOT.exists():
        return []
    cutoff = datetime.date.today() - datetime.timedelta(days=STALE_DAYS)
    out = []
    for day_dir in WORKDIR_ROOT.iterdir():
        if not day_dir.is_dir():
            continue
        try:
            day = datetime.date.fromisoformat(day_dir.name)
        except ValueError:
            continue
        if day <= cutoff:
            out.append(str(day_dir))
    return out

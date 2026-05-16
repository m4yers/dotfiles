"""Workdir lifecycle (engine-internal).

A workdir is a per-run scratch directory under
``<base_dir>/<date>/<slug>/``. One workdir = one run. If a workdir
with the same slug already exists for today, it is dropped and
recreated (running the workflow with the same dir wipes prior state).

Engine never lists or sweeps workdirs as part of plan execution; that
is left to the application or to manual cleanup.
"""
from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from slugify import slugify

# Default slug length cap. Applications may pass a different value
# via create_workdir(slug_max_length=...).
DEFAULT_SLUG_MAX_LENGTH = 60


def today() -> str:
    return datetime.date.today().isoformat()


def create_workdir(
    base_dir: str | Path,
    basename: str,
    slug_max_length: int = DEFAULT_SLUG_MAX_LENGTH,
) -> Path:
    """Resolve ``<base_dir>/<date>/<slug>/`` and create it fresh.

    If the resolved path already exists, it is removed and recreated.
    One workdir always corresponds to exactly one run.
    """
    root = Path(base_dir)
    slug = slugify(basename, max_length=slug_max_length)
    wd = root / today() / slug
    if wd.exists():
        shutil.rmtree(wd)
    wd.mkdir(parents=True)
    return wd


def sweep(path: str | Path) -> dict:
    """Delete a single workdir. Refuses paths whose first three
    components don't match an obvious workdir shape (base/date/slug)
    to limit blast radius from misuse.

    Returns a summary dict with the removed path (if any).
    """
    p = Path(path).resolve()
    parts = p.parts
    if len(parts) < 3:
        raise ValueError(f"path is too shallow to be a workdir: {path}")
    # crude shape check: penultimate component looks like a date.
    date_part = parts[-2]
    try:
        datetime.date.fromisoformat(date_part)
    except ValueError:
        raise ValueError(
            f"penultimate component {date_part!r} is not an ISO date — "
            f"refusing to sweep {path}")
    removed: list[str] = []
    if p.exists():
        shutil.rmtree(p)
        removed.append(str(p))
    return {"removed": removed, "ok": True}

"""Curator tunables and helpers.

Owns curator-specific constants: workdir base dir and the basename
derivation rule applied to ingest URLs/paths. Engine gets these via
parameters from runtime.py — engine itself is config-free.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

# Workdir base — engine creates per-run dirs under here.
WORKDIR_ROOT = "/tmp/curator"


def derive_basename(url_or_path: str) -> str:
    """Derive a stable basename for the workdir slug.

    URLs: take the path's last segment; fall back to host.
    File paths: take the file stem.
    """
    parsed = urlparse(url_or_path)
    if parsed.scheme in ("http", "https"):
        # URL: use the last path segment, otherwise the host.
        last = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        return last or parsed.netloc or "ingest"
    # File path
    p = Path(url_or_path)
    return p.stem or p.name or "ingest"

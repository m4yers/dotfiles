"""Curator tunables and helpers.

Owns curator-specific constants: workdir base dir and the basename
derivation rule applied to ingest URLs/paths. Engine gets these via
parameters from runtime.py — engine itself is config-free.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Workdir base — engine creates per-run dirs under here.
WORKDIR_ROOT = "/tmp/curator"


# URL last-path segments that carry no identity (the actual id
# lives in the query string). When we see one of these we fall
# back to host+last rather than just last to avoid collisions
# (every YouTube watch URL would otherwise collapse to "watch").
_GENERIC_PATH_SEGMENTS = frozenset({
    "watch", "view", "index", "video", "play",
})


def derive_basename(url_or_path: str) -> str:
    """Derive a stable basename for the workdir slug.

    URLs:
      - youtube.com/watch?v=ID  → ``youtube-<ID>``
      - youtube.com/playlist?list=ID → ``youtube-list-<ID>``
      - youtu.be/ID             → ``youtube-<ID>``
      - other URLs              → last path segment, guarded
                                   against generic verbs by
                                   prepending the host short name.
                                   Falls back to host alone.

    File paths: take the file stem.
    """
    parsed = urlparse(url_or_path)
    if parsed.scheme in ("http", "https"):
        host = (parsed.netloc or "").lower()

        # ── YouTube specifically ─────────────────────────
        if "youtube.com" in host:
            qs = parse_qs(parsed.query)
            vid = (qs.get("v") or [""])[0]
            if vid:
                return f"youtube-{vid}"
            list_id = (qs.get("list") or [""])[0]
            if list_id:
                return f"youtube-list-{list_id}"
        if host == "youtu.be":
            vid = parsed.path.strip("/").split("/", 1)[0]
            if vid:
                return f"youtube-{vid}"

        # ── Generic URL ──────────────────────────────────
        last = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        if not last:
            return host or "ingest"

        # If the last segment is a known generic verb, the real
        # identity must live in the query string — prepend the
        # host short name so two such URLs do not collide on the
        # workdir slug.
        if last in _GENERIC_PATH_SEGMENTS:
            host_short = (host.replace("www.", "")
                              .split(".", 1)[0])
            return f"{host_short}-{last}" if host_short else last

        return last

    # ── Local file path ─────────────────────────────────
    p = Path(url_or_path)
    return p.stem or p.name or "ingest"

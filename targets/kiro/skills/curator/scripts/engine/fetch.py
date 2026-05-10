"""Fetch dispatcher. Routes URL or local path to the right handler."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from engine import workdir
from engine.handlers import html, local, pdf, youtube


def fetch(url_or_path: str, topic: str | None = None) -> dict:
    """Dispatch and invoke the appropriate handler.

    Returns: {path, type, basename, workdir, origin} where `path` is
    vault-relative, `workdir` is absolute.
    """
    handler = _dispatch(url_or_path)

    # Create the workdir up front. Handlers may populate meta.json.
    # We use a provisional slug from the URL/path; the handler refines
    # the basename after downloading.
    provisional = _provisional_basename(url_or_path)
    wd = workdir.create_workdir(provisional)

    result = handler(url_or_path, wd, topic=topic)
    # Handler must fill: path, type, basename.
    result["workdir"] = str(wd)
    result["origin"] = url_or_path
    return result


def _dispatch(url_or_path: str):
    # Local path?
    p = Path(url_or_path).expanduser()
    if p.exists() and p.is_file():
        return local.handle

    # URL?
    parsed = urlparse(url_or_path)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"not a URL or existing file: {url_or_path}")

    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if "youtube.com" in host or host == "youtu.be":
        return youtube.handle
    if host == "arxiv.org" and (path.startswith("/abs/") or path.startswith("/pdf/")):
        return pdf.handle
    if path.lower().endswith(".pdf"):
        return pdf.handle
    return html.handle


def _provisional_basename(url_or_path: str) -> str:
    p = Path(url_or_path)
    if p.exists():
        return p.stem
    parsed = urlparse(url_or_path)
    last = Path(parsed.path).name or parsed.netloc or "source"
    # Strip extension and query junk.
    last = re.sub(r"[?#].*$", "", last)
    last = re.sub(r"\.(pdf|html|md|htm)$", "", last, flags=re.I)
    return last or "source"

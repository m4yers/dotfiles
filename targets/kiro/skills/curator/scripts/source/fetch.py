"""Fetch dispatcher. Routes URL or local path to the right handler.

The caller supplies the workdir (created by ``disk.sh workdir
create``) so the source tool has no workdir-lifecycle concern — it
only writes content into the vault (``10 SOURCES/...``) and an
optional meta.json into the given workdir.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from source import content_types
from source.errors import (
    HandlerError, HandlerErrorCode, _error_envelope,
)
from source.handlers import html, local, pdf, youtube


def fetch(
    url_or_path: str,
    workdir: Path,
    topic: str | None = None,
    media_override: str | None = None,
) -> dict:
    """Dispatch and invoke the appropriate handler.

    Success:
      {ok: True, path, type, content_type, basename, workdir, origin}
      where ``path`` is vault-relative. ``media_override``, when set,
      replaces the handler-classified ``content_type`` unconditionally.

    Failure: handler error envelope augmented with ``origin`` and
    ``workdir`` so the orchestrator can still sweep or retry.
    """
    if media_override is not None:
        content_types.validate(media_override)

    try:
        handler = _dispatch(url_or_path)
    except HandlerError as e:
        env = _error_envelope("fetch", e.code, e.message, e.details)
        env["origin"] = url_or_path
        env["workdir"] = str(workdir)
        return env

    result = handler(url_or_path, workdir, topic=topic)
    result["workdir"] = str(workdir)
    result["origin"] = url_or_path
    if media_override is not None and result.get("ok", True):
        result["content_type"] = media_override
    return result


def _dispatch(url_or_path: str):
    # Local path?
    p = Path(url_or_path).expanduser()
    if p.exists() and p.is_file():
        return local.handle

    # URL?
    parsed = urlparse(url_or_path)
    if parsed.scheme not in ("http", "https"):
        raise HandlerError(
            HandlerErrorCode.PARSE_ERROR,
            f"not a URL or existing file: {url_or_path}",
            {"input": url_or_path},
        )

    host = (parsed.netloc or "").lower()
    path = parsed.path or ""

    if "youtube.com" in host or host == "youtu.be":
        return youtube.handle
    if host == "arxiv.org" and (path.startswith("/abs/") or path.startswith("/pdf/")):
        return pdf.handle
    if path.lower().endswith(".pdf"):
        return pdf.handle
    return html.handle

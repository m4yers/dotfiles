"""Public fetch + convert pipeline.

``fetch`` dispatches a URL or local path to the right handler under
``handlers/`` and returns the resulting envelope. ``convert`` reads a
fetched artifact and produces the normalized markdown the extractors
will consume, plus a metadata dict for downstream tasks.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml
from pypdf import PdfReader

from curator import vault
from curator.source.errors import (
    HandlerError,
    HandlerErrorCode,
    error_envelope,
)
from curator.source.handlers import (
    handle_gdrive,
    handle_html,
    handle_local,
    handle_pdf,
    handle_youtube,
)


# ── fetch ───────────────────────────────────────────────


def fetch(url_or_path: str) -> dict:
    """Dispatch and invoke the appropriate handler.

    Success::

        {ok: True, path, type, content_type, basename, origin}

    where ``path`` is the absolute path of the saved artifact.
    ``content_type`` here is the handler's best guess from URL /
    extension / metadata; downstream tasks may re-derive it from
    source content.

    Failure: handler error envelope augmented with ``origin``.
    """
    try:
        handler = _dispatch(url_or_path)
    except HandlerError as e:
        env = error_envelope("fetch", e.code, e.message, e.details)
        env["origin"] = url_or_path
        return env

    # Handlers expect a scratch dir for intermediate work (yt-dlp
    # downloads etc.). Engine doesn't allocate one for the fetch
    # CLI; /tmp is fine because all canonical artifacts land in the
    # vault.
    result = handler(url_or_path, Path("/tmp"))
    if result.get("ok", True) and "path" in result:
        result["path"] = str(vault.abs_path(result["path"]))
    result["origin"] = url_or_path
    return result


def _dispatch(url_or_path: str):
    # Local path?
    p = Path(url_or_path).expanduser()
    if p.exists() and p.is_file():
        return handle_local

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
        return handle_youtube
    if host == "drive.google.com":
        return handle_gdrive
    if (host == "arxiv.org"
            and (path.startswith("/abs/")
                 or path.startswith("/pdf/"))):
        return handle_pdf
    if path.lower().endswith(".pdf"):
        return handle_pdf
    return handle_html


# ── convert ─────────────────────────────────────────────


def convert(path: str, task_workdir: str | Path) -> dict:
    """Extract metadata + normalized text for source at ``path``.

    ``path`` may be vault-relative or absolute. Writes normalized
    text to ``<task_workdir>/source.md``. Returns the output.yaml
    content as a dict (caller serializes to stdout).

    Output shape::

        media:           article|pdf|video|audio|...
        vault_path:      absolute path of the source in the vault
        converted_path:  absolute path of the extracted markdown
        metadata:        free-form per-format dict (frontmatter for
                          markdown, /Title etc. for PDF, plus title /
                          authors / language / origin_url / etc.).
                          For web sources, also includes http_headers
                          captured by the fetch handler.
    """
    p = _resolve(path)
    if not p.exists():
        raise FileNotFoundError(path)

    tw = Path(task_workdir)
    tw.mkdir(parents=True, exist_ok=True)
    source_md = tw / "source.md"

    ext = p.suffix.lower()
    metadata: dict = {}

    if ext == ".md":
        raw = p.read_text(encoding="utf-8")
        fm, body = vault.parse(raw)
        source_md.write_text(body, encoding="utf-8")
        # Frontmatter becomes the bulk of metadata; keep
        # title/authors/language as named keys for downstream
        # convenience.
        metadata = dict(fm)
        if "title" not in metadata:
            metadata["title"] = p.stem
        media = "article"
    elif ext == ".pdf":
        reader = PdfReader(str(p))
        source_md.write_text(_pdf_to_text(reader), encoding="utf-8")
        meta = reader.metadata or {}
        title = str(meta.get("/Title") or p.stem)
        author_str = str(meta.get("/Author") or "")
        authors = ([a.strip() for a in author_str.split(",")
                     if a.strip()]
                    if author_str else [])
        metadata = {
            "title":      title,
            "authors":    authors,
            "language":   str(meta.get("/Language") or ""),
            "page_count": len(reader.pages),
            "producer":   str(meta.get("/Producer") or ""),
            "subject":    str(meta.get("/Subject") or ""),
        }
        media = "pdf"
    elif ext in (".html", ".htm"):
        raw = p.read_text(encoding="utf-8")
        # HTML fetcher already normalized to markdown at fetch time.
        fm, body = vault.parse(raw)
        source_md.write_text(body, encoding="utf-8")
        metadata = dict(fm)
        if "title" not in metadata:
            metadata["title"] = p.stem
        media = "article"
    elif ext == ".epub":
        raise NotImplementedError("epub conversion not implemented in v1")
    else:
        raise ValueError(f"cannot convert: {ext}")

    # If the fetch task captured http_headers (web sources), pull
    # them in from its output.yaml sibling.
    fetch_out = tw.parent / "fetch" / "output.yaml"
    if fetch_out.exists():
        try:
            fetch_data = yaml.safe_load(
                fetch_out.read_text(encoding="utf-8"))
            if isinstance(fetch_data, dict) \
                    and "http_headers" in fetch_data:
                metadata["http_headers"] = fetch_data["http_headers"]
        except Exception:
            # Don't fail convert because fetch output is malformed.
            pass

    return {
        "media":          media,
        "vault_path":     str(p),
        "converted_path": str(source_md.resolve()),
        "metadata":       metadata,
    }


def emit_convert(path: str, task_workdir: str) -> None:
    """CLI entrypoint: print output.yaml to stdout."""
    result = convert(path, task_workdir)
    print(yaml.safe_dump(result, sort_keys=False, allow_unicode=True,
                            default_flow_style=False), end="")


def _resolve(path: str) -> Path:
    """Vault-relative or absolute → absolute Path."""
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    candidate = vault.VAULT_ROOT / path
    if candidate.exists():
        return candidate.resolve()
    return p.resolve()


def _pdf_to_text(reader: PdfReader) -> str:
    """Extract text from a PDF. Preserves page breaks."""
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as e:
            txt = f"[extraction error on page {i+1}: {e}]"
        parts.append(f"<!-- page {i+1} -->\n{txt.strip()}")
    return "\n\n---\n\n".join(parts)

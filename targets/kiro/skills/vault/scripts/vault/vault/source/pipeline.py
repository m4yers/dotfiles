"""Public fetch + convert pipeline.

``fetch`` dispatches a URL or local path to the right handler under
``handlers/`` and returns the resulting envelope. ``convert`` reads a
fetched artifact and produces the normalized markdown the extractors
will consume, plus a metadata dict for downstream tasks.

Both share a per-artifact cache dir under ``SOURCE_CACHE_DIR``:
``fetch`` persists its envelope there as ``fetch.yaml`` and
``convert`` reads it back and writes ``source.md`` beside it, so the
caller never carries temp paths between the two commands.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from vault import SOURCES_DIR, VAULT_ROOT, abs_path, parse  # noqa: F401
from vault.source.config import SOURCE_CACHE_DIR
from vault.source.errors import (
    HandlerError,
    HandlerErrorCode,
    error_envelope,
)
from vault.source.handlers import (
    handle_gdrive,
    handle_html,
    handle_local,
    handle_pdf,
    handle_youtube,
)


# ── cache ───────────────────────────────────────────────


def cache_dir(artifact_abs: Path) -> Path:
    """Per-artifact cache dir, keyed by a hash of the absolute path
    so renames in the vault never alias two artifacts."""
    key = hashlib.sha1(str(artifact_abs).encode("utf-8")).hexdigest()
    return SOURCE_CACHE_DIR / key


def _persist_fetch(result: dict) -> Path:
    """Write the fetch envelope to ``<cache>/fetch.yaml``."""
    d = cache_dir(Path(result["path"]))
    d.mkdir(parents=True, exist_ok=True)
    fp = d / "fetch.yaml"
    fp.write_text(yaml.safe_dump(result, sort_keys=False,
                                 allow_unicode=True,
                                 default_flow_style=False),
                  encoding="utf-8")
    return fp


def _load_fetch(artifact_abs: Path) -> tuple[dict | None, Path | None]:
    """Return ``(envelope, path)`` of a persisted fetch envelope, or
    ``(None, None)`` when the artifact was never fetched through this
    tool. A present but unreadable file raises ``ValueError``."""
    fp = cache_dir(artifact_abs) / "fetch.yaml"
    if not fp.exists():
        return None, None
    try:
        data = yaml.safe_load(fp.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ValueError(
            f"fetch envelope unreadable: {fp}: "
            f"{type(e).__name__}: {e}")
    if not isinstance(data, dict):
        raise ValueError(f"fetch envelope {fp} is not a mapping")
    return data, fp


# ── fetch ───────────────────────────────────────────────


def fetch(url_or_path: str) -> dict:
    """Dispatch and invoke the appropriate handler.

    Success::

        {
          ok: True,
          path:         absolute path of the saved artifact,
          type:         handler kind (article|paper|video|book|...),
          content_type: handler's best guess; downstream may re-derive,
          basename:     slugified filename stem,
          origin:       the url_or_path given,
          fetch_envelope: path of the persisted copy of this envelope,
          # optional, handler-dependent:
          http_headers:   {<header>: <value>}  (html handler),
          reused:         True when the artifact already existed and
                          no write happened (every handler, via
                          reused_envelope),
          image_failures: {count, urls}  (html handler; images that
                          failed to download),
        }

    Failure: handler error envelope augmented with ``origin``.
    """
    try:
        handler = _dispatch(url_or_path)
    except HandlerError as e:
        env = error_envelope("fetch", e.code, e.message, e.details)
        env["origin"] = url_or_path
        return env

    # Handlers expect a scratch dir for intermediate work (yt-dlp
    # downloads etc.). The vault CLI does not allocate one for the
    # fetch command; /tmp is fine because all canonical artifacts
    # land in the vault.
    result = handler(url_or_path, Path("/tmp"))
    result["origin"] = url_or_path
    if result.get("ok", True) and "path" in result:
        result["path"] = str(abs_path(result["path"]))
        result["fetch_envelope"] = str(_persist_fetch(result))
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


def convert(path: str) -> dict:
    """Extract metadata + normalized text for source at ``path``.

    ``path`` may be vault-relative or absolute. Writes normalized
    text to ``<cache>/source.md`` and, when ``fetch`` persisted an
    envelope for this artifact, copies its ``http_headers`` into
    ``metadata``. Raises ``FileNotFoundError`` when the source is
    absent and ``ValueError`` (message ``cannot convert <path>:
    <reason>``) for unsupported or unreadable formats, including a
    PDF with no extractable text.

    Output shape::

        media:           article|pdf|video|audio|...
        vault_path:      absolute path of the source in the vault
        converted_path:  absolute path of the extracted markdown
        fetch_envelope:  path of the fetch envelope used, or null
        metadata:        free-form per-format dict (frontmatter for
                          markdown, /Title etc. for PDF, plus title /
                          authors / language / origin_url / etc.).
                          With a fetch envelope, also includes the
                          http_headers captured by the fetch handler.
    """
    p = _resolve(path)
    if not p.exists():
        raise FileNotFoundError(path)

    fetch_data, fetch_path = _load_fetch(p)

    source_md = cache_dir(p) / "source.md"

    ext = p.suffix.lower()
    metadata: dict = {}

    if ext == ".md":
        raw = p.read_text(encoding="utf-8")
        fm, body = parse(raw)
        _write(source_md, body)
        # Frontmatter becomes the bulk of metadata; keep
        # title/authors/language as named keys for downstream
        # convenience.
        metadata = dict(fm)
        if "title" not in metadata:
            metadata["title"] = p.stem
        media = "article"
    elif ext == ".pdf":
        try:
            reader = PdfReader(str(p))
            text = _pdf_to_text(reader)
            meta = reader.metadata or {}
            page_count = len(reader.pages)
        except PyPdfError as e:
            raise ValueError(
                f"cannot convert {path}: corrupt or unsupported PDF: "
                f"{e}")
        if not _has_text(text):
            raise ValueError(
                f"cannot convert {path}: PDF has no extractable text "
                f"(scanned? run OCR first)")
        _write(source_md, text)
        title = str(meta.get("/Title") or p.stem)
        author_str = str(meta.get("/Author") or "")
        authors = ([a.strip() for a in author_str.split(",")
                     if a.strip()]
                    if author_str else [])
        metadata = {
            "title":      title,
            "authors":    authors,
            "language":   str(meta.get("/Language") or ""),
            "page_count": page_count,
            "producer":   str(meta.get("/Producer") or ""),
            "subject":    str(meta.get("/Subject") or ""),
        }
        media = "pdf"
    elif ext in (".html", ".htm"):
        raw = p.read_text(encoding="utf-8")
        # HTML fetcher already normalized to markdown at fetch time.
        fm, body = parse(raw)
        _write(source_md, body)
        metadata = dict(fm)
        if "title" not in metadata:
            metadata["title"] = p.stem
        media = "article"
    elif ext == ".epub":
        raise ValueError(
            f"cannot convert {path}: epub is not supported yet; "
            f"export the book to PDF and convert that instead")
    else:
        raise ValueError(f"cannot convert {path}: unsupported "
                         f"extension {ext or '(none)'}")

    if fetch_data is not None and "http_headers" in fetch_data:
        metadata["http_headers"] = fetch_data["http_headers"]

    return {
        "media":          media,
        "vault_path":     str(p),
        "converted_path": str(source_md.resolve()),
        "fetch_envelope": str(fetch_path) if fetch_path else None,
        "metadata":       metadata,
    }


def _write(target: Path, text: str) -> None:
    """Write ``text`` to ``target``, creating the cache dir only once
    a format has been accepted so failed conversions leave nothing."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def emit_convert(path: str) -> None:
    """CLI entrypoint: print output.yaml to stdout."""
    result = convert(path)
    print(yaml.safe_dump(result, sort_keys=False, allow_unicode=True,
                            default_flow_style=False), end="")


def _resolve(path: str) -> Path:
    """Vault-relative or absolute → absolute Path."""
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    candidate = VAULT_ROOT / path
    if candidate.exists():
        return candidate.resolve()
    return p.resolve()


_PAGE_MARKER = "<!-- page "


def _has_text(pdf_text: str) -> bool:
    """True when the extracted PDF text holds anything beyond the
    page markers and extraction-error notes ``_pdf_to_text`` adds."""
    for line in pdf_text.splitlines():
        s = line.strip()
        if (not s or s == "---" or s.startswith(_PAGE_MARKER)
                or s.startswith("[extraction error on page")):
            continue
        return True
    return False


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

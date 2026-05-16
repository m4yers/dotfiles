"""Curator source acquisition — fetch + convert.

Single-file replacement of the former source/ sub-package.
Sections (in order):
    errors        : exception types per content variant
    config        : tunables (chunk size, etc.)
    content_types : declared content kinds
    handlers      : html, pdf, youtube, local fetch+convert routines
    fetch / convert : public entrypoints
    CLI           : typer app exposing fetch and convert commands

All CLI output is YAML on stdout (the task-runner contract).
"""
from __future__ import annotations

import arxiv
import contextlib
import datetime
import functools
import hashlib
import httpx
import io
import json
import mimetypes
import re
import shutil
import subprocess
import trafilatura
import webvtt
import yaml
import yt_dlp

from curator import vault
from curator.utils import emit, fail
from pathlib import Path
from pypdf import PdfReader
from trafilatura.metadata import extract_metadata
from typing import Any, Callable
from urllib.parse import urljoin, urlparse
from urllib.parse import urlparse


# ── errors ────────────────────────────────────────────




class HandlerErrorCode:
    """Finite set of error categories returned by handlers.

    Kept as a class of constants rather than an ``enum.Enum`` so the
    strings appear unchanged in JSON output and so adding a new code
    never breaks existing consumers that pattern-match on literals.
    """

    # Remote fetch: we got no answer or an error answer.
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    NETWORK_HTTP_ERROR = "NETWORK_HTTP_ERROR"
    NETWORK_CONNECT_ERROR = "NETWORK_CONNECT_ERROR"

    # Remote fetch: we got content, but it is unusable for our purpose
    # (no captions on a video, trafilatura extracted nothing, …).
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"

    # Malformed URL, JSON, or other input the handler cannot parse.
    PARSE_ERROR = "PARSE_ERROR"

    # A local file input has a suffix we do not handle.
    UNSUPPORTED_FORMAT = "UNSUPPORTED_FORMAT"

    # A local file input does not exist.
    FILE_NOT_FOUND = "FILE_NOT_FOUND"

    # Path escapes the vault, or target folder is not writable.
    VAULT_ERROR = "VAULT_ERROR"

    # The source already lives in the vault — fetch refuses to
    # duplicate. Envelope includes the existing path.
    ALREADY_EXISTS = "ALREADY_EXISTS"

    # A subprocess (yt-dlp, pdftotext, …) exited non-zero. Distinct
    # from NETWORK_* because the error originates locally.
    EXTERNAL_TOOL_ERROR = "EXTERNAL_TOOL_ERROR"

    # Catch-all for anything the decorator could not classify. Keep
    # small — every time this fires the right fix is usually to add a
    # more specific mapping above.
    INTERNAL_ERROR = "INTERNAL_ERROR"


class HandlerError(Exception):
    """Raised inside a handler when a failure cleanly maps to a code.

    Use this when the handler already knows which category applies; it
    is preferred over raising ``ValueError``/``FileNotFoundError`` and
    letting the decorator guess.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _error_envelope(handler: str, code: str, message: str,
                    details: dict[str, Any] | None = None) -> dict:
    env: dict[str, Any] = {
        "ok": False,
        "error": {
            "code": code,
            "handler": handler,
            "message": message,
        },
    }
    if details:
        env["error"]["details"] = details
    return env


def safe_handler(handler_name: str) -> Callable[[Callable[..., dict]], Callable[..., dict]]:
    """Wrap a handler's ``handle()`` function with uniform error mapping.

    The wrapped function always returns a dict:

    - Success: the handler's own dict plus ``ok: True`` (added if the
      handler did not set it).
    - Failure: the standard error envelope.

    The decorator catches:

    - ``HandlerError`` — passed through with its own code and details.
    - ``httpx.TimeoutException`` → ``NETWORK_TIMEOUT``
    - ``httpx.HTTPStatusError`` → ``NETWORK_HTTP_ERROR`` (includes the
      status code in ``details``).
    - ``httpx.ConnectError`` / ``httpx.RequestError`` (non-timeout) →
      ``NETWORK_CONNECT_ERROR``
    - ``subprocess.TimeoutExpired`` → ``EXTERNAL_TOOL_ERROR`` with
      ``details.kind = "timeout"``
    - ``subprocess.CalledProcessError`` → ``EXTERNAL_TOOL_ERROR`` with
      ``details.returncode``
    - ``FileNotFoundError`` → ``FILE_NOT_FOUND``
    - ``ValueError`` → ``PARSE_ERROR`` (handlers should prefer raising
      ``HandlerError`` with a more specific code; ``ValueError`` is the
      fallback).
    - Anything else → ``INTERNAL_ERROR``.
    """

    def _decorator(fn: Callable[..., dict]) -> Callable[..., dict]:
        @functools.wraps(fn)
        def _wrapped(*args, **kwargs) -> dict:
            try:
                result = fn(*args, **kwargs)
            except HandlerError as e:
                return _error_envelope(
                    handler_name, e.code, e.message, e.details
                )
            except httpx.TimeoutException as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.NETWORK_TIMEOUT,
                    f"remote fetch timed out: {e}",
                )
            except httpx.HTTPStatusError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.NETWORK_HTTP_ERROR,
                    f"remote returned HTTP {e.response.status_code}",
                    {"status_code": e.response.status_code,
                     "url": str(e.request.url)},
                )
            except (httpx.ConnectError, httpx.RequestError) as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.NETWORK_CONNECT_ERROR,
                    f"connection error: {e}",
                )
            except subprocess.TimeoutExpired as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.EXTERNAL_TOOL_ERROR,
                    f"{e.cmd[0] if e.cmd else 'subprocess'} timed out after {e.timeout}s",
                    {"kind": "timeout",
                     "timeout_s": e.timeout,
                     "cmd": list(e.cmd) if e.cmd else None},
                )
            except subprocess.CalledProcessError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.EXTERNAL_TOOL_ERROR,
                    f"{e.cmd[0] if e.cmd else 'subprocess'} exited {e.returncode}",
                    {"kind": "nonzero",
                     "returncode": e.returncode,
                     "cmd": list(e.cmd) if e.cmd else None,
                     "stderr": (e.stderr or "")[:500] if isinstance(e.stderr, str) else None},
                )
            except FileNotFoundError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.FILE_NOT_FOUND,
                    f"file not found: {e}",
                )
            except PermissionError as e:
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.VAULT_ERROR,
                    f"permission denied: {e}",
                )
            except ValueError as e:
                # Handlers should prefer HandlerError(PARSE_ERROR, ...)
                # with details; plain ValueError is the fallback.
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.PARSE_ERROR,
                    str(e),
                )
            except Exception as e:  # noqa: BLE001 — last-resort safety net
                return _error_envelope(
                    handler_name,
                    HandlerErrorCode.INTERNAL_ERROR,
                    f"unhandled {type(e).__name__}: {e}",
                )

            # Success — ensure ok: True is present.
            if not isinstance(result, dict):
                raise TypeError(
                    f"handler {handler_name!r} returned non-dict: {type(result)}"
                )
            result.setdefault("ok", True)
            return result

        return _wrapped

    return _decorator

# ── config ────────────────────────────────────────────
# ── Fetch / HTTP ──────────────────────────────────────────────────────

# All timeouts in seconds. Values tuned for interactive use: short
# enough to notice wedged requests, long enough to survive arxiv's
# occasional slow responses.
HTTP_TIMEOUT_HTML = 45
HTTP_TIMEOUT_PDF = 60
HTTP_TIMEOUT_IMAGE = 30

# Subprocess timeouts for yt-dlp are now managed through the
# ``socket_timeout`` option inside the Python API in
# ``handlers/youtube.py``; the legacy YTDLP_*_TIMEOUT constants are
# no longer needed here.

# ── Basename / slug ───────────────────────────────────────────────────

# Image filename hash prefix length. 8 hex chars = 32 bits; collision
# risk within a single article's image set is vanishingly small and
# the file stays human-readable.
IMG_HASH_PREFIX = 8

# Short-title window for arxiv basenames. 60 chars fits in a typical
# filesystem row and covers most paper titles without chopping a word.
ARXIV_SHORT_TITLE_MAX = 60

# ── content_types ─────────────────────────────────────

CONTENT_TYPES: frozenset[str] = frozenset({
    "paper",
    "book",
    "article",
    "lecture",
    "talk",
    "podcast",
    "video",
    "movie",
    "audio",
    "unknown",
})


def validate(content_type: str) -> str:
    """Return ``content_type`` unchanged if valid; raise otherwise."""
    if content_type not in CONTENT_TYPES:
        raise ValueError(
            f"content_type must be one of {sorted(CONTENT_TYPES)}, "
            f"got {content_type!r}"
        )
    return content_type

# ── handlers/html ─────────────────────────────────────


def _reused_envelope(dest_rel: str, type_: str, basename: str) -> dict:
    """Return a success envelope for a source that already lives in
    the vault. Skips the write step; downstream tasks see ok: true and
    the existing path."""
    return {
        "ok": True,
        "reused": True,
        "path": dest_rel,
        "type": type_,
        "content_type": type_,
        "basename": basename,
    }




ARTICLES_DIR = f"{vault.SOURCES_DIR}/Articles"


@safe_handler("html")
def handle_html(url: str, wd: Path) -> dict:
    """Fetch, extract, download images, save."""
    r = httpx.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT_HTML, headers={"User-Agent": "curator/0.1"})
    r.raise_for_status()
    html = r.text
    final_url = str(r.url)
    # Capture HTTP headers we care about for downstream metadata.
    http_headers = {
        k.lower(): v for k, v in r.headers.items()
        if k.lower() in ("content-type", "last-modified", "etag",
                          "date", "server", "content-language")
    }

    md = trafilatura.extract(
        html,
        url=final_url,
        output_format="markdown",
        include_links=True,
        include_images=True,
        with_metadata=False,
    )
    if not md:
        raise HandlerError(
            HandlerErrorCode.SOURCE_UNAVAILABLE,
            "trafilatura returned no content",
            {"url": final_url},
        )

    meta = extract_metadata(html, default_url=final_url)
    title = (meta.title if meta else None) or _title_from_url(final_url)
    author = (meta.author if meta else None) or _host_slug(final_url)
    basename = vault.slugify_basename(f"{author} - {title}")

    dest_rel, _exists = _html_dest(basename)
    if _exists:
        return _reused_envelope(dest_rel, "article", basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    # Download images, rewrite paths.
    assets_dir = dest_abs.parent / f"{basename}.assets"
    md, image_log = _localize_images(md, final_url, assets_dir, wd)

    fm = {
        "type": "source",
        "origin_url": url,
        "fetched_at": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z",
        "author": author,
        "published_date": getattr(meta, "date", None) if meta else None,
        "last_updated": datetime.date.today().isoformat(),
    }
    body = f"# {title}\n\n{md}\n"
    dest_abs.write_text(vault.serialize(fm, body), encoding="utf-8")

    (wd / "meta.json").write_text(
        json.dumps(
            {"origin_url": url, "final_url": final_url, "images": image_log}, indent=2
        )
    )

    return {
        "path": dest_rel,
        "type": "article",
        "content_type": "article",
        "basename": basename,
        "http_headers": http_headers,
    }


_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _localize_images(md: str, base_url: str, assets_dir: Path, wd: Path) -> tuple[str, list[dict]]:
    """Download every ![]() image, rewrite src to local path, return log."""
    log = []
    urls_seen = {}

    def _sub(match):
        alt, src = match.group(1), match.group(2)
        if src.startswith("data:"):
            return match.group(0)
        abs_url = urljoin(base_url, src)
        if abs_url in urls_seen:
            local = urls_seen[abs_url]
        else:
            local = _download_image(abs_url, assets_dir)
            urls_seen[abs_url] = local
        if local is None:
            log.append({"url": abs_url, "status": "failed"})
            return match.group(0)
        log.append({"url": abs_url, "local": str(local.name), "status": "ok"})
        # Wikilink works better in Obsidian: ![[<basename>.assets/img.png]]
        rel_ref = f"{assets_dir.name}/{local.name}"
        return f"![{alt}]({rel_ref})"

    return _IMG_RE.sub(_sub, md), log


def _download_image(url: str, assets_dir: Path) -> Path | None:
    try:
        r = httpx.get(
            url,
            follow_redirects=True,
            timeout=HTTP_TIMEOUT_IMAGE,
            headers={"User-Agent": "curator/0.1"},
        )
        r.raise_for_status()
    except Exception:
        return None
    content_type = r.headers.get("content-type", "")
    ext = _ext_from_content_type(content_type) or Path(urlparse(url).path).suffix or ".bin"
    digest = hashlib.sha256(r.content).hexdigest()[:IMG_HASH_PREFIX]
    fname = f"img-{digest}{ext}"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / fname
    dest.write_bytes(r.content)
    return dest


def _ext_from_content_type(ct: str) -> str | None:
    ct = ct.split(";")[0].strip().lower()
    # Stdlib covers the common image MIME types and stays current with
    # additions; no hand-rolled map.
    return mimetypes.guess_extension(ct)


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    last = Path(parsed.path).name or parsed.netloc
    return re.sub(r"[-_]+", " ", re.sub(r"\.html?$", "", last)).strip() or "Untitled"


def _host_slug(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "").split(".")[0]
    return host or "web"


def _html_dest(basename: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{ARTICLES_DIR}/{basename}.md"
    return candidate, vault.abs_path(candidate).exists()

# ── handlers/pdf ──────────────────────────────────────




PAPERS_DIR = f"{vault.SOURCES_DIR}/Papers"


@safe_handler("pdf")
def handle_pdf(url: str, wd: Path) -> dict:
    """Download PDF, compute stable basename, write meta."""
    parsed = urlparse(url)
    is_arxiv = parsed.netloc == "arxiv.org" and (
        parsed.path.startswith("/abs/") or parsed.path.startswith("/pdf/")
    )

    if is_arxiv:
        basename, pdf_url = _resolve_arxiv(url)
    else:
        pdf_url = url
        basename = _basename_from_url(url)

    basename = vault.slugify_basename(basename)
    dest_rel, _exists = _pdf_dest(basename)
    if _exists:
        return _reused_envelope(dest_rel, "paper", basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream(
        "GET",
        pdf_url,
        follow_redirects=True,
        timeout=HTTP_TIMEOUT_PDF,
        headers={"User-Agent": "curator/0.1"},
    ) as r:
        r.raise_for_status()
        with open(dest_abs, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)

    # Record meta.
    meta = {"origin_url": url, "resolved_pdf_url": pdf_url, "size_bytes": dest_abs.stat().st_size}
    (wd / "meta.json").write_text(json.dumps(meta, indent=2))

    return {
        "path": dest_rel,
        "type": "pdf",
        "content_type": "paper",
        "basename": basename,
    }


def _resolve_arxiv(url: str) -> tuple[str, str]:
    """Return (basename, pdf_url) for an arxiv /abs/ or /pdf/ URL.

    Basename shape: '<id> - <first-author-et-al> - <short-title>'.
    Falls back to just the arxiv id if the metadata lookup fails
    (API rate limit, transient network error, etc.).

    Uses the ``arxiv`` Python library, which wraps the official arxiv
    API — more robust than scraping the abstract page's meta tags and
    respects arxiv's rate-limit guidance automatically.
    """
    m = re.search(r"arxiv\.org/(abs|pdf)/([\d\.]+)", url)
    if not m:
        raise HandlerError(
            HandlerErrorCode.PARSE_ERROR,
            f"unparseable arxiv url: {url}",
            {"url": url},
        )
    arxiv_id = m.group(2).rstrip(".pdf")
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    basename = arxiv_id  # fallback when the API lookup fails
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(arxiv.Client().results(search))
        title = re.sub(r"\s+", " ", paper.title).strip()
        if paper.authors:
            first = paper.authors[0].name.split(",")[0].strip()
            suffix = "" if len(paper.authors) == 1 else " et al"
            short_title = title[:ARXIV_SHORT_TITLE_MAX].rstrip()
            basename = f"{arxiv_id} - {first}{suffix} - {short_title}"
    except Exception:
        # Rate limit, network timeout, arxiv-id not found — any of
        # these falls back to the id-only basename, which is still
        # a stable filename.
        pass

    return basename, pdf_url


def _basename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name or "source"


def _pdf_dest(basename: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{PAPERS_DIR}/{basename}.pdf"
    return candidate, vault.abs_path(candidate).exists()

# ── handlers/youtube ──────────────────────────────────




VIDEOS_DIR = f"{vault.SOURCES_DIR}/Videos"

# Anchor the running transcript with a [MM:SS] marker each time the
# next cue crosses this many seconds past the previous anchor. 30s
# is a good compromise between readable prose and citeable moments.
ANCHOR_EVERY_SECONDS = 30


# Socket timeout in seconds for every yt-dlp network operation.
# Tuned the same way the previous subprocess timeouts were — short
# enough to notice a wedged request, long enough to survive a slow
# caption download.
YTDLP_SOCKET_TIMEOUT = 60


@safe_handler("youtube")
def handle_youtube(url: str, wd: Path) -> dict:
    """Download transcript and thumbnail, emit source.md."""
    meta = _fetch_meta(url)
    channel = meta.get("channel") or meta.get("uploader") or "unknown"
    title = meta.get("title") or "untitled"
    basename = vault.slugify_basename(f"{channel} - {title}")

    dest_rel, _exists = _youtube_dest(basename)
    if _exists:
        return _reused_envelope(dest_rel, "video", basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    transcript = _fetch_transcript(url, wd)
    body = _build_source_md(url, meta, transcript)

    dest_abs.write_text(body, encoding="utf-8")

    # Thumbnail to .assets/
    assets_dir = dest_abs.parent / f"{basename}.assets"
    _fetch_thumbnail(url, assets_dir, wd)

    (wd / "meta.json").write_text(json.dumps(meta, indent=2))

    return {
        "path": dest_rel,
        "type": "video",
        "content_type": _classify_content_type(meta),
        "basename": basename,
    }


# Classifier heuristics. Signals flow from strongest (explicit title
# keyword) to weakest (duration + category). The goal is a cheap,
# deterministic default — classifier task supersedes downstream.
_DURATION_LONG_FORM_S = 40 * 60   # 40 minutes
_TITLE_KEYWORDS_PODCAST = ("interview", "podcast", "in conversation")
_TITLE_KEYWORDS_TALK = ("keynote", " talk", "conference", "tedx", "ted talk")
_TITLE_KEYWORDS_LECTURE = ("lecture", "class ", "course", "seminar")


def _classify_content_type(meta: dict) -> str:
    """Infer content_type from yt-dlp meta.

    Priority:
      1. explicit title keyword (podcast / talk / lecture)
      2. long-form + Education category → lecture
      3. long-form only → podcast (long-form uploads with no
         education signal are most often podcasts or interviews)
      4. otherwise → video
    """
    title = (meta.get("title") or "").lower()
    duration = meta.get("duration") or 0
    categories = [c.lower() for c in (meta.get("categories") or [])]

    if any(k in title for k in _TITLE_KEYWORDS_PODCAST):
        return "podcast"
    if any(k in title for k in _TITLE_KEYWORDS_TALK):
        return "talk"
    if any(k in title for k in _TITLE_KEYWORDS_LECTURE):
        return "lecture"

    if duration and duration > _DURATION_LONG_FORM_S:
        if "education" in categories:
            return "lecture"
        return "podcast"

    return "video"


def _fetch_meta(url: str) -> dict:
    """yt-dlp extract_info (skip_download) → info dict."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "socket_timeout": YTDLP_SOCKET_TIMEOUT,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        raise HandlerError(
            HandlerErrorCode.EXTERNAL_TOOL_ERROR,
            f"yt-dlp meta failed: {e}",
            {"kind": "yt-dlp", "op": "meta"},
        ) from e
    return info or {}


def _fetch_transcript(url: str, wd: Path) -> str:
    """Download subtitles (manual preferred, auto as fallback), return
    plain text with [MM:SS] anchors every ~30s.

    yt-dlp writes VTT files named by video id into ``sub_path``. We
    discover them via glob after each attempt.
    """
    sub_path = wd / "subs"
    sub_path.mkdir(exist_ok=True)
    outtmpl = str(sub_path / "%(id)s.%(ext)s")

    # Try manual subs first, then auto-subs as fallback.
    attempts = [
        {"writesubtitles": True,  "writeautomaticsub": False},
        {"writesubtitles": False, "writeautomaticsub": True},
    ]
    for flags in attempts:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "subtitleslangs": ["en.*", "en"],
            "subtitlesformat": "vtt",
            "outtmpl": outtmpl,
            "socket_timeout": YTDLP_SOCKET_TIMEOUT,
            **flags,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError:
            # This attempt failed — try the next flag combo. We only
            # raise SOURCE_UNAVAILABLE if both manual and auto fail.
            continue
        vtts = list(sub_path.glob("*.vtt"))
        if vtts:
            return _vtt_to_anchored_text(vtts[0].read_text(encoding="utf-8"))

    raise HandlerError(
        HandlerErrorCode.SOURCE_UNAVAILABLE,
        "no subtitles or auto-subs available",
        {"url": url},
    )


def _fetch_thumbnail(url: str, assets_dir: Path, wd: Path) -> None:
    """Download the video thumbnail into assets_dir. Non-fatal on
    failure — the rest of the handler proceeds without it."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writethumbnail": True,
        "outtmpl": str(assets_dir / "thumbnail.%(ext)s"),
        "socket_timeout": YTDLP_SOCKET_TIMEOUT,
        "postprocessors": [{
            "key": "FFmpegThumbnailsConvertor",
            "format": "jpg",
        }],
    }
    with contextlib.suppress(Exception):
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])


def _vtt_to_anchored_text(vtt: str) -> str:
    """Flatten a VTT transcript into plain text with [MM:SS] markers.

    Delegates cue parsing to ``webvtt-py``, which handles WEBVTT /
    NOTE / Kind / Language headers, cue settings, multi-line cue
    text, and timestamp normalization across comma vs dot separators.
    We then walk the cues in order and emit a [MM:SS] anchor each
    time a cue starts ``ANCHOR_EVERY_SECONDS`` past the previous
    anchor.
    """
    out: list[str] = []
    last_mark = -1
    for cap in webvtt.read_buffer(io.StringIO(vtt)):
        total_s = int(cap.start_in_seconds)
        bucket = total_s // ANCHOR_EVERY_SECONDS
        if bucket != last_mark // ANCHOR_EVERY_SECONDS:
            mm, ss = divmod(total_s, 60)
            out.append(f"\n[{mm:02d}:{ss:02d}] ")
            last_mark = total_s
        # cue text may be multi-line; collapse to a single space run
        # so the anchored paragraph reads cleanly.
        out.append(cap.text.replace("\n", " ").strip() + " ")
    return "".join(out).strip()


def _build_source_md(url: str, meta: dict, transcript: str) -> str:
    fm = {
        "type": "source",
        "origin_url": url,
        "fetched_at": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z",
        "channel": meta.get("channel") or meta.get("uploader"),
        "uploaded": meta.get("upload_date"),
        "duration": meta.get("duration"),
        "last_updated": datetime.date.today().isoformat(),
    }
    body = f"# {meta.get('title', 'untitled')}\n\n{transcript}\n"
    return vault.serialize(fm, body)


def _youtube_dest(basename: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{VIDEOS_DIR}/{basename}"
    return candidate, vault.abs_path(candidate).exists()

# ── handlers/local ────────────────────────────────────



EXT_TO_FOLDER = {
    ".pdf": f"{vault.SOURCES_DIR}/Papers",
    ".epub": f"{vault.SOURCES_DIR}/Books",
    ".md": f"{vault.SOURCES_DIR}/Articles",
    ".markdown": f"{vault.SOURCES_DIR}/Articles",
}


@safe_handler("local")
def handle_local(path_str: str, wd: Path) -> dict:
    src = Path(path_str).expanduser().resolve()
    if not src.is_file():
        raise HandlerError(
            HandlerErrorCode.FILE_NOT_FOUND,
            f"local file not found: {path_str}",
            {"path": path_str},
        )

    ext = src.suffix.lower()
    if ext not in EXT_TO_FOLDER:
        raise HandlerError(
            HandlerErrorCode.UNSUPPORTED_FORMAT,
            f"unsupported local extension: {ext}",
            {"path": path_str, "ext": ext,
             "supported": sorted(EXT_TO_FOLDER.keys())},
        )

    # Already inside vault?
    vault_root = vault.VAULT_ROOT.resolve()
    try:
        rel = src.relative_to(vault_root)
        rel_s = str(rel)
    except ValueError:
        rel_s = None

    if rel_s and rel_s.startswith(vault.SOURCES_DIR + "/"):
        basename = src.stem
        type_ = _type_from_ext(ext)
        return {
            "path": rel_s,
            "type": type_,
            "content_type": _content_type_from_ext(ext),
            "basename": basename,
        }

    # Copy into the right folder.
    basename = vault.slugify_basename(src.stem)
    folder = EXT_TO_FOLDER[ext]
    dest_rel, _exists = _local_dest(folder, basename, ext)
    if _exists:
        return _reused_envelope(dest_rel, type_, basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_abs)

    return {
        "path": dest_rel,
        "type": _type_from_ext(ext),
        "content_type": _content_type_from_ext(ext),
        "basename": basename,
    }


def _type_from_ext(ext: str) -> str:
    return {
        ".pdf": "pdf",
        ".epub": "epub",
        ".md": "article",
        ".markdown": "article",
    }.get(ext, "unknown")


def _content_type_from_ext(ext: str) -> str:
    """Map file extension to content_type.

    Kept minimal because the local handler is a pass-through — the
    classifier task downstream re-derives content from source (e.g. a
    .pdf that is a book, or a .md that is a paper draft).
    """
    return {
        ".pdf": "paper",
        ".epub": "book",
        ".md": "article",
        ".markdown": "article",
    }.get(ext, "unknown")


def _local_dest(folder: str, basename: str, ext: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{folder}/{basename}{ext}"
    return candidate, vault.abs_path(candidate).exists()

# ── fetch ─────────────────────────────────────────────




def fetch(url_or_path: str) -> dict:
    """Dispatch and invoke the appropriate handler.

    Success:
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
        env = _error_envelope("fetch", e.code, e.message, e.details)
        env["origin"] = url_or_path
        return env

    # Handlers expect a scratch dir for intermediate work (yt-dlp
    # downloads etc.). Engine doesn't allocate one for the fetch CLI;
    # /tmp is fine because all canonical artifacts land in the vault.
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
    if host == "arxiv.org" and (path.startswith("/abs/") or path.startswith("/pdf/")):
        return handle_pdf
    if path.lower().endswith(".pdf"):
        return handle_pdf
    return handle_html




# ── convert ───────────────────────────────────────────





def convert(path: str, task_workdir: str | Path) -> dict:
    """Extract metadata + normalized text for source at ``path``.

    ``path`` may be vault-relative or absolute. Writes normalized
    text to ``<task_workdir>/source.md``. Returns the output.yaml
    content as a dict (caller serializes to stdout).

    Output shape:
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
        # Frontmatter becomes the bulk of metadata; keep title/authors/
        # language as named keys for downstream convenience.
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
        authors = [a.strip() for a in author_str.split(",") if a.strip()] \
                  if author_str else []
        metadata = {
            "title":       title,
            "authors":     authors,
            "language":    str(meta.get("/Language") or ""),
            "page_count":  len(reader.pages),
            "producer":    str(meta.get("/Producer") or ""),
            "subject":     str(meta.get("/Subject") or ""),
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

    # If the fetch task captured http_headers (web sources), pull them
    # in from its output.yaml sibling.
    fetch_out = tw.parent / "fetch" / "output.yaml"
    if fetch_out.exists():
        try:
            fetch_data = yaml.safe_load(fetch_out.read_text(encoding="utf-8"))
            if isinstance(fetch_data, dict) and "http_headers" in fetch_data:
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





# ── CLI ──────────────────────────────────────────────────────────

import json as _json
from typing import Annotated as _Annotated

import typer as _typer



def cli_fetch(
    url_or_path: _Annotated[str, _typer.Argument(
        help="URL or local file path to fetch.")],
) -> None:
    """Acquire a source. Writes the artifact into the vault and emits
    a fetch envelope on stdout."""
    result = fetch(url_or_path)
    emit(result)
    if not result.get("ok", True):
        raise _typer.Exit(code=1)


def cli_convert(
    path: _Annotated[str, _typer.Argument(
        help="Vault-relative or absolute path to the source file.")],
    task_workdir: _Annotated[str, _typer.Option(
        "--task-workdir",
        help="The convert task's subdir; receives source.md sibling.")],
) -> None:
    """Read source, extract metadata, write source.md sibling, emit
    output.yaml on stdout."""
    try:
        emit_convert(path, task_workdir)
    except FileNotFoundError as e:
        fail(f"not found: {e}")
    except ValueError as e:
        fail(str(e))


app = _typer.Typer(
    help="Curator source — fetch + convert.",
    no_args_is_help=True,
)
app.command("fetch")(cli_fetch)
app.command("convert")(cli_convert)

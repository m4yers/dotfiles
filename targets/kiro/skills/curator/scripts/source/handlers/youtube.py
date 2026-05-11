"""YouTube handler. Fetches transcript via yt-dlp (Python API), saves as 10 SOURCES/Videos/<basename>.md."""
from __future__ import annotations

import contextlib
import datetime
import io
import json
from pathlib import Path

import webvtt
import yt_dlp

from vault import vault
from source.errors import HandlerError, HandlerErrorCode, safe_handler

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
def handle(url: str, wd: Path, topic: str | None = None) -> dict:
    """Download transcript and thumbnail, emit source.md."""
    meta = _fetch_meta(url)
    channel = meta.get("channel") or meta.get("uploader") or "unknown"
    title = meta.get("title") or "untitled"
    basename = vault.slugify_basename(f"{channel} - {title}")

    dest_rel = _unique_dest(basename)
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
# deterministic default — the user can always override with --media.
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


def _unique_dest(basename: str) -> str:
    candidate = f"{VIDEOS_DIR}/{basename}.md"
    if not vault.abs_path(candidate).exists():
        return candidate
    n = 2
    while True:
        candidate = f"{VIDEOS_DIR}/{basename} ({n}).md"
        if not vault.abs_path(candidate).exists():
            return candidate
        n += 1

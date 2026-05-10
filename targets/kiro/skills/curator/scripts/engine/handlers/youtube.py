"""YouTube handler. Fetches transcript via yt-dlp, saves as 10 SOURCES/Videos/<basename>.md."""
from __future__ import annotations

import datetime
import json
import re
import subprocess
from pathlib import Path

from engine import vault
from engine.config import (
    YTDLP_META_TIMEOUT,
    YTDLP_THUMBNAIL_TIMEOUT,
    YTDLP_TRANSCRIPT_TIMEOUT,
)

VIDEOS_DIR = f"{vault.SOURCES_DIR}/Videos"


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
        "basename": basename,
    }


def _fetch_meta(url: str) -> dict:
    """yt-dlp -j --skip-download → JSON metadata."""
    r = subprocess.run(
        ["yt-dlp", "-j", "--skip-download", url],
        capture_output=True,
        text=True,
        timeout=YTDLP_META_TIMEOUT,
    )
    if r.returncode != 0:
        raise ValueError(f"yt-dlp meta failed: {r.stderr.strip()}")
    return json.loads(r.stdout.strip().splitlines()[0])


def _fetch_transcript(url: str, wd: Path) -> str:
    """Download subtitles (manual preferred, auto as fallback), return plain text
    with [MM:SS] anchors every ~30s."""
    sub_path = wd / "subs"
    sub_path.mkdir(exist_ok=True)
    # Try manual subs first.
    for flag in ("--write-subs", "--write-auto-subs"):
        r = subprocess.run(
            [
                "yt-dlp",
                flag,
                "--skip-download",
                "--sub-langs", "en.*,en",
                "--sub-format", "vtt",
                "--output", str(sub_path / "%(id)s.%(ext)s"),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=YTDLP_TRANSCRIPT_TIMEOUT,
        )
        if r.returncode == 0:
            vtts = list(sub_path.glob("*.vtt"))
            if vtts:
                return _vtt_to_anchored_text(vtts[0].read_text(encoding="utf-8"))
    raise ValueError("no subtitles or auto-subs available")


def _vtt_to_anchored_text(vtt: str) -> str:
    """Strip VTT headers, emit plain text with [MM:SS] markers every ~30s."""
    lines = vtt.splitlines()
    out = []
    last_mark = -1
    current_ts = None
    ts_re = re.compile(r"^(\d+):(\d{2}):(\d{2})[.,]\d+\s+-->")
    for ln in lines:
        if ts_re.match(ln):
            h, m, s = ts_re.match(ln).groups()
            total_s = int(h) * 3600 + int(m) * 60 + int(s)
            current_ts = total_s
            continue
        if ln.strip().startswith(("WEBVTT", "NOTE", "Kind:", "Language:")):
            continue
        if not ln.strip():
            continue
        # Anchor every 30s.
        if current_ts is not None and current_ts // 30 != last_mark // 30:
            mm = current_ts // 60
            ss = current_ts % 60
            out.append(f"\n[{mm:02d}:{ss:02d}] ")
            last_mark = current_ts
        out.append(ln.strip() + " ")
    return "".join(out).strip()


def _fetch_thumbnail(url: str, assets_dir: Path, wd: Path):
    assets_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "yt-dlp",
            "--write-thumbnail",
            "--skip-download",
            "--convert-thumbnails", "jpg",
            "--output", str(assets_dir / "thumbnail.%(ext)s"),
            url,
        ],
        capture_output=True,
        text=True,
        timeout=YTDLP_THUMBNAIL_TIMEOUT,
    )


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

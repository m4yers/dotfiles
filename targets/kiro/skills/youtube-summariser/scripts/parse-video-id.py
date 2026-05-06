#!/usr/bin/env python3
"""Extract a YouTube video ID from a URL or bare ID.

Prints the 11-character video ID to stdout.
Exits 1 if the input cannot be parsed.

Supported formats:
  youtube.com/watch?v=XXXXXXXXXXX
  youtu.be/XXXXXXXXXXX
  youtube.com/embed/XXXXXXXXXXX
  bare 11-char ID
"""
import re
import sys
from urllib.parse import parse_qs, urlparse


def extract_video_id(raw: str) -> str | None:
    raw = raw.strip()
    # Bare ID: 11 chars, alphanumeric + dash + underscore
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw):
        return raw
    parsed = urlparse(raw)
    if parsed.hostname in ("youtu.be",):
        vid = parsed.path.lstrip("/")
        if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            return vid
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        if parsed.path.startswith("/embed/"):
            vid = parsed.path.split("/embed/")[1].split("/")[0]
            if re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
                return vid
        vid = parse_qs(parsed.query).get("v", [None])[0]
        if vid and re.fullmatch(r"[A-Za-z0-9_-]{11}", vid):
            return vid
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: parse-video-id.py <URL or ID>", file=sys.stderr)
        sys.exit(1)
    vid = extract_video_id(sys.argv[1])
    if vid is None:
        print(f"Cannot extract video ID from: {sys.argv[1]}",
              file=sys.stderr)
        sys.exit(1)
    print(vid)


if __name__ == "__main__":
    main()

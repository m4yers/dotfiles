"""Canonical content types for curator sources.

Transport type (``pdf`` / ``youtube`` / ``html`` / ``local``) answers
*how* to fetch; content type (``paper`` / ``book`` / ``article`` /
``lecture`` / ``talk`` / ``podcast`` / ``video`` / ``movie`` /
``audio`` / ``unknown``) answers *what shape* of summary the
extractor should produce. The two are orthogonal — the same PDF
transport can hold a paper or a book; a YouTube URL can point at a
lecture, a talk, or a podcast episode.

Handlers classify deterministically from the evidence they already
have (URL, PDF metadata, yt-dlp info dict, file extension). When the
handler cannot tell, it returns ``unknown`` and the user can override
with ``source.sh fetch --media <type>``.
"""
from __future__ import annotations

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

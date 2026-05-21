"""Tests for curator.source.pipeline._dispatch — URL → handler routing.

Pure function: no network, no filesystem. Confirms the dispatch
table covers each handler's expected URL shapes and falls back to
HTML for anything else.
"""
from __future__ import annotations

import pytest

from curator.source.handlers import (
    handle_gdrive,
    handle_html,
    handle_local,
    handle_pdf,
    handle_youtube,
)
from curator.source.errors import HandlerError
from curator.source.pipeline import _dispatch


@pytest.mark.parametrize(
    "url, expected",
    [
        # Google Drive: every shape gdown understands.
        ("https://drive.google.com/file/d/1JW6Q_wwvBjMz9xzOtTldFfPiF7BrdEeQ/view",
         handle_gdrive),
        ("https://drive.google.com/file/d/1JW6Q_wwvBjMz9xzOtTldFfPiF7BrdEeQ/preview",
         handle_gdrive),
        ("https://drive.google.com/uc?id=1JW6Q_wwvBjMz9xzOtTldFfPiF7BrdEeQ",
         handle_gdrive),
        ("https://drive.google.com/open?id=1JW6Q_wwvBjMz9xzOtTldFfPiF7BrdEeQ",
         handle_gdrive),

        # YouTube — youtube.com or youtu.be hosts.
        ("https://www.youtube.com/watch?v=abc123", handle_youtube),
        ("https://youtu.be/abc123",                handle_youtube),

        # Arxiv — /abs/ and /pdf/ paths route to PDF handler with
        # arxiv-aware basename derivation.
        ("https://arxiv.org/abs/2507.13334",     handle_pdf),
        ("https://arxiv.org/pdf/2507.13334.pdf", handle_pdf),

        # Generic .pdf URL.
        ("https://example.com/papers/foo.pdf", handle_pdf),

        # HTML fallback — anything else.
        ("https://example.com/article",                 handle_html),
        ("https://www.scribd.com/document/123/Foo-Bar", handle_html),
    ],
)
def test_dispatch_routes_to_expected_handler(url, expected):
    assert _dispatch(url) is expected


def test_dispatch_local_file(tmp_path):
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"%PDF-1.4 stub")
    assert _dispatch(str(src)) is handle_local


def test_dispatch_rejects_non_url_non_path():
    with pytest.raises(HandlerError):
        _dispatch("not a url and no such file")

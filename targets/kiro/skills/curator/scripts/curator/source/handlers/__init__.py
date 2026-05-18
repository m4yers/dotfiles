"""Per-source-type handlers.

Each handler is a function decorated with ``@safe_handler(...)`` so
exceptions are mapped to the canonical error envelope. ``pipeline``
imports them directly to dispatch by URL/path shape.
"""
from __future__ import annotations

from curator.source.handlers.html    import handle_html
from curator.source.handlers.local   import handle_local
from curator.source.handlers.pdf     import handle_pdf
from curator.source.handlers.youtube import handle_youtube


__all__ = [
    "handle_html",
    "handle_local",
    "handle_pdf",
    "handle_youtube",
]

"""Source subpackage — public re-exports.

External callers (``__main__``) only need ``source.app`` for the
CLI mount. Internal sub-modules import errors / pipeline / config
directly.
"""
from __future__ import annotations

from curator.source.cli import app


__all__ = ["app"]

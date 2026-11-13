"""Source subpackage — public re-exports.

External callers (``vault.cli``) only need ``source.app`` for the
CLI mount. Internal sub-modules import errors / pipeline / config
directly.
"""
from __future__ import annotations

from vault.source.cli import app


__all__ = ["app"]

"""Source acquisition tunables + content-type vocabulary.

Per-handler timeouts, slug constants, and the canonical
``CONTENT_TYPES`` set live here. Sub-modules under ``handlers/``
import only what they need; this file has no internal imports.
"""
from __future__ import annotations


# ── HTTP timeouts (seconds) ─────────────────────────────
#
# Values tuned for interactive use: short enough to notice wedged
# requests, long enough to survive arxiv's occasional slow
# responses.

HTTP_TIMEOUT_HTML  = 45
HTTP_TIMEOUT_PDF   = 60
HTTP_TIMEOUT_IMAGE = 30


# ── basename / slug ─────────────────────────────────────

# Image filename hash prefix length. 8 hex chars = 32 bits;
# collision risk within a single article's image set is vanishingly
# small and the file stays human-readable.
IMG_HASH_PREFIX = 8

# Short-title window for arxiv basenames. 60 chars fits in a typical
# filesystem row and covers most paper titles without chopping a
# word.
ARXIV_SHORT_TITLE_MAX = 60


# ── yt-dlp ──────────────────────────────────────────────

# Socket timeout in seconds for every yt-dlp network operation.
# 60s tolerates yt-dlp's TLS handshake plus initial range request
# on slow networks while still surfacing wedged sockets within a
# minute.
YTDLP_SOCKET_TIMEOUT = 60

# Anchor the running transcript with a [MM:SS] marker each time the
# next cue crosses this many seconds past the previous anchor. 30s
# is a good compromise between readable prose and citeable moments.
ANCHOR_EVERY_SECONDS = 30

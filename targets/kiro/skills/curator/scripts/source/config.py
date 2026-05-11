"""Sourcer tool tunables.

HTTP + yt-dlp timeouts and slug / hash limits used by the fetch
handlers.
"""

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

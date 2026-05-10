"""Centralised numeric constants with justifying comments.

Every tuning knob lives here so changes have one obvious home and the
rationale is not buried in the call sites. Import from engine.config.
"""

# ── Staleness thresholds ──────────────────────────────────────────────

# Workdir cleanup: /tmp/curator/<date>/ older than this is purged on
# sweep --all. 3 days lines up with macOS /tmp retention; enough to
# debug yesterday's ingest, short enough to keep /tmp tidy.
WORKDIR_STALE_DAYS = 3

# Page staleness: last_updated older than this surfaces in lint `stale`.
# 90 days ~= one quarter; pages untouched for a full quarter are flagged
# for a refresh pass.
PAGE_STALE_DAYS = 90


# ── Vault scans ───────────────────────────────────────────────────────

# Stub detection: body (after frontmatter) shorter than this is a stub.
# 50 chars ~= a title + one sentence; below this a page carries no
# semantic content beyond the filename.
STUB_BODY_MIN = 50

# Context-build skip: files larger than this skip alias extraction to
# avoid parsing megabyte source notes whose aliases rarely matter for
# dedup. 10 KB is the 99th percentile of existing atomic pages in the
# user's vault.
CONTEXT_FAST_PARSE_LIMIT = 10_000


# ── Fetch / HTTP ──────────────────────────────────────────────────────

# All timeouts in seconds. Values tuned for interactive use: short
# enough to notice wedged requests, long enough to survive arxiv's
# occasional slow responses.
HTTP_TIMEOUT_HTML = 45
HTTP_TIMEOUT_PDF = 60
HTTP_TIMEOUT_IMAGE = 30
HTTP_TIMEOUT_ARXIV_META = 20

# Subprocess timeouts for yt-dlp (seconds). Meta is quick; transcript
# download can fetch the full caption track and occasional thumbnails,
# so it gets more headroom.
YTDLP_META_TIMEOUT = 60
YTDLP_TRANSCRIPT_TIMEOUT = 120
YTDLP_THUMBNAIL_TIMEOUT = 60


# ── Basename / slug ───────────────────────────────────────────────────

# Cap on slugify output for workdir names. 80 chars keeps /tmp paths
# well under shell argv limits while retaining enough of the source
# title to be recognisable.
SLUG_MAX_LENGTH = 80

# Image filename hash prefix length. 8 hex chars = 32 bits; collision
# risk within a single article's image set is vanishingly small and
# the file stays human-readable.
IMG_HASH_PREFIX = 8

# Short-title window for arxiv basenames. 60 chars fits in a typical
# filesystem row and covers most paper titles without chopping a word.
ARXIV_SHORT_TITLE_MAX = 60

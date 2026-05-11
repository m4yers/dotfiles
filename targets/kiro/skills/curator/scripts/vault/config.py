"""Vault tool tunables.

Each curator tool (disk / source / vault) owns a separate config
module so it carries only the knobs its own code consults. Every
value has a comment explaining why its current setting is what it is.
"""

# ── Vault scans ───────────────────────────────────────────────────────

# Page staleness: last_updated older than this surfaces in lint `stale`.
# 90 days ~= one quarter; pages untouched for a full quarter are flagged
# for a refresh pass.
PAGE_STALE_DAYS = 90

# Stub detection: body (after frontmatter) shorter than this is a stub.
# 50 chars ~= a title + one sentence; below this a page carries no
# semantic content beyond the filename.
STUB_BODY_MIN = 50

# Context-build skip: files larger than this skip alias extraction to
# avoid parsing megabyte source notes whose aliases rarely matter for
# dedup. 10 KB is the 99th percentile of existing atomic pages in the
# user's vault.
CONTEXT_FAST_PARSE_LIMIT = 10_000

"""Disk tool tunables.

Workdir lifecycle + slug length. Schemas consumed by disk live at
``scripts/disk/schemas/`` and are loaded inside each
builder's write path.
"""

# Workdir cleanup: /tmp/curator/<date>/ older than this is purged on
# `workdir sweep --all`. 3 days lines up with macOS /tmp retention;
# enough to debug yesterday's ingest, short enough to keep /tmp tidy.
WORKDIR_STALE_DAYS = 3

# Cap on slugify output for workdir names. 80 chars keeps /tmp paths
# well under shell argv limits while retaining enough of the source
# title to be recognisable.
SLUG_MAX_LENGTH = 80

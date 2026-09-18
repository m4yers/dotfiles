"""Shared JMESPath grammar regexes for the statically-projectable subset.

Both engine/mapping.py (dispatch-time projection walker) and
validate/subtype.py (init-time subtype-projection static pass) walk
JMESPath paths using the same subset: an identifier optionally followed
by any number of ``[<integer>]`` index accessors. Anything outside this
shape (filters, wildcards, functions, quoted keys, arithmetic) is
deliberately non-projectable and fails closed at both surfaces.

Keeping the two regexes in one module keeps the static-vs-runtime
projection subsets in lock step — a grammar drift here would silently
let one side project shapes the other rejects.
"""
from __future__ import annotations

import re


# Path segment: identifier optionally followed by any number of
# ``[<integer>]`` index accessors.
SEGMENT_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*)((?:\[\d+\])*)$")

# Bracket-index accessor: ``[<int>]``. Enumerates the indices on a
# segment tail after the leading identifier match.
INDEX_RE = re.compile(r"\[(\d+)\]")

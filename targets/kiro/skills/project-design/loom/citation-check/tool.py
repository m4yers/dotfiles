"""Tool body for the `citation-check` task (loomv2 native contract).

Deterministic verifier for line-anchored code citations in the design
markdown (`path/to/file.ext:123` or `:123-456`). A line-anchored
citation is an unambiguous claim about EXISTING code, so a missing
file or an out-of-range line is a hard miss that forces the design
loop to revise (via design-review-merge).

Deliberately NOT checked (they cannot be distinguished from proposed
new code): bare file mentions without line numbers, and
`Class::member` symbol references.

Runs inside the design review loop region, so every design revision
is re-checked.

The engine loads this module in-process and calls `citation_check`;
all YAML IO and schema validation is engine-owned.
"""

from __future__ import annotations

import os
import re

from io_types import CitationCheckInput, CitationCheckOutput

# path/to/file.ext:123 or path/to/file.ext:123-456 (also en-dash).
_CITE_RE = re.compile(
    r"(?P<path>[A-Za-z0-9_][A-Za-z0-9_./-]*\.[A-Za-z0-9]{1,6}):"
    r"(?P<start>\d+)(?:[-\u2013](?P<end>\d+))?"
)

_SKIP_DIRS = {".git", "build", "node_modules", ".venv", "__pycache__"}

# Line-anchor checks make no sense for these (version numbers etc.).
_SKIP_EXTS = {".0", ".1", ".2", ".3", ".4", ".5", ".6", ".7", ".8", ".9"}


def _line_count(path: str) -> int:
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def _basename_index(workspace: str) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            index.setdefault(name, []).append(os.path.join(root, name))
    return index


def citation_check(inp: CitationCheckInput) -> CitationCheckOutput:
    ws = inp.workspace_abs
    index: dict[str, list[str]] | None = None  # built lazily

    seen: set[str] = set()
    misses: list[dict] = []
    checked = 0

    for m in _CITE_RE.finditer(inp.design or ""):
        cite = m.group(0)
        if cite in seen:
            continue
        seen.add(cite)
        rel, start = m.group("path"), int(m.group("start"))
        end = int(m.group("end")) if m.group("end") else start
        if os.path.splitext(rel)[1] in _SKIP_EXTS:
            continue
        checked += 1

        # Resolve: direct relative path, else unique basename match.
        cand = os.path.join(ws, rel)
        if not os.path.isfile(cand):
            if index is None:
                index = _basename_index(ws)
            matches = [
                p for p in index.get(os.path.basename(rel), [])
                if p.endswith(os.sep + rel) or os.path.basename(rel) == rel
            ]
            if len(matches) == 1:
                cand = matches[0]
            elif not matches:
                misses.append({
                    "citation": cite,
                    "kind": "missing_file",
                    "detail": f"no file named {os.path.basename(rel)!r} "
                              "anywhere in the workspace",
                })
                continue
            else:
                # Ambiguous basename: pick any match whose line range
                # fits; miss only when none fits.
                if any(_line_count(p) >= end for p in matches):
                    continue
                misses.append({
                    "citation": cite,
                    "kind": "line_out_of_range",
                    "detail": f"{len(matches)} files match "
                              f"{os.path.basename(rel)!r}; none has "
                              f">= {end} lines",
                })
                continue

        total = _line_count(cand)
        if end > total:
            misses.append({
                "citation": cite,
                "kind": "line_out_of_range",
                "detail": f"{os.path.relpath(cand, ws)} has {total} lines",
            })

    return CitationCheckOutput(
        checked=checked,
        misses=misses,
        ok=not misses,
        report="" if not misses else "\n".join(
            f"- {x['citation']}: {x['kind']} ({x['detail']})"
            for x in misses
        ),
    )

"""Deduplicate findings on (file_line, title) match.

Replaces the old deduplicate-findings.py script. Same input/
output shape as before, but called as a Python function from
pipeline.cli_assemble rather than a CLI subprocess.
"""
from __future__ import annotations

from typing import Iterable


def deduplicate(findings: Iterable[dict]) -> list[dict]:
    """Return findings with exact (file_line, title) duplicates removed.

    First-seen wins. Order is preserved across the input.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for f in findings:
        key = (f.get("file_line", ""), f.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out

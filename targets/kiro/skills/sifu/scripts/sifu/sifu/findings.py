"""Merge findings that cite the same rule at the same file.

The primary is the first-seen finding; the other sites go into
``also_at`` and the merged confidence is the maximum. Order is
preserved across the input.
"""
from __future__ import annotations

from typing import Iterable


def _file(file_line: str) -> str:
    return file_line.rsplit(":", 1)[0] if ":" in file_line else file_line


def merge(findings: Iterable[dict]) -> list[dict]:
    groups: dict[tuple[str, str], dict] = {}
    out: list[dict] = []
    for f in findings:
        key = (f.get("check_id", ""), _file(f.get("file_line", "")))
        primary = groups.get(key)
        if primary is None:
            primary = {**f, "also_at": list(f.get("also_at") or [])}
            groups[key] = primary
            out.append(primary)
            continue
        site = f.get("file_line", "")
        if site and site != primary["file_line"] and site not in primary["also_at"]:
            primary["also_at"].append(site)
        primary["confidence"] = max(primary["confidence"], f["confidence"])
    return out

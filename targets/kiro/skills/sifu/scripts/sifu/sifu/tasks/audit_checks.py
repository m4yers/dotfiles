"""Tool task: the review checks for a skill.

Parses sifu's annotated references (sifu.rules), keeps the files whose
``Applies`` meets the detected topics, drops autocheck-backed rules and
those below the Info band, and orders by severity within file order.
"""
from __future__ import annotations

from sifu import rules

# Reference order: cross-cutting files first, then the type file(s).
_FILE_ORDER = ["AUT", "STY", "CMP", "TRG", "MOD", "SCR", "SEC", "RUL",
               "WFL", "IFC", "TOL", "REF", "FLW"]


def run(topics: list[str]) -> dict:
    refs = sorted(rules.rule_files(),
                  key=lambda r: _FILE_ORDER.index(r["code"])
                  if r["code"] in _FILE_ORDER else len(_FILE_ORDER))
    checks = rules.select(refs, topics)
    return {"checks": checks, "total": len(checks)}

"""Autochecks for references/rule-codes.md (rule annotations).

Apply only to references that declare a ``**Code:**`` header, so skills
without annotated conventions are untouched. The grammar lives in
``sifu.rules``; these rules surface its ``problems`` as findings.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from sifu import rules
from sifu.autochecks._helpers import Finding, rule


def _annotated(refs_dir: Path) -> list[dict]:
    """Parsed references that declare (or try to declare) a code."""
    out = []
    for p in sorted(refs_dir.glob("*.md")):
        parsed = rules.parse_file(p, f"references/{p.name}")
        head = p.read_text(encoding="utf-8").splitlines()[:6]
        if parsed["code"] or any(l.startswith("**Code:**") for l in head):
            out.append(parsed)
    return out


def _problems(refs_dir: Path, needle: str) -> List[Finding]:
    return [
        Finding(f"references/{r['path'].name}", line, msg)
        for r in _annotated(refs_dir)
        for line, msg in r["problems"] if needle in msg
    ]


@rule("RUL-1-1")
def rule_1_1_file_code(refs_dir: Path) -> List[Finding]:
    """Annotated references MUST declare a unique three-letter code.

    Rule: RUL-1-1
    """
    findings = _problems(refs_dir, "Code:")
    seen: dict[str, str] = {}
    for r in _annotated(refs_dir):
        if r["code"] in seen:
            findings.append(Finding(
                f"references/{r['path'].name}", 1,
                f"code {r['code']} already used by {seen[r['code']]}"))
        elif r["code"]:
            seen[r["code"]] = r["path"].name
    return findings


@rule("RUL-1-2")
def rule_1_2_code_matches_position(refs_dir: Path) -> List[Finding]:
    """Every numbered rule MUST carry an annotation matching its position.

    Rule: RUL-1-2
    """
    return (_problems(refs_dir, "lacks a")
            + _problems(refs_dir, "sits at")
            + _problems(refs_dir, "file code is"))


@rule("RUL-1-3")
def rule_1_3_applies_header(refs_dir: Path) -> List[Finding]:
    """Annotated references MUST declare an Applies header.

    Rule: RUL-1-3
    """
    return [
        Finding(f"references/{r['path'].name}", 1, "missing **Applies:** header")
        for r in _annotated(refs_dir) if r["code"] and not r["applies"]
    ]


@rule("RUL-2-2")
def rule_2_2_severity_in_range(refs_dir: Path) -> List[Finding]:
    """Annotated severity MUST lie in the keyword's reachable range.

    Rule: RUL-2-2
    """
    return _problems(refs_dir, "outside")

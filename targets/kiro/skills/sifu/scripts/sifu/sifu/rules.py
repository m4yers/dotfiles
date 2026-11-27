"""Parse annotated conventions references into checks.

Grammar (references/rule-codes.md): a rule file declares
``**Code:** XXX`` and ``**Applies:** t1, t2`` under its H1; every
numbered rule starts ``(rule: XXX-<section>-<rule>, severity: <n>)``.
Checks are ``schemas/check.yaml`` dicts; ``severity_of`` is the lookup
autochecks and the report use so one annotation feeds every consumer.
"""
from __future__ import annotations

import re
from pathlib import Path

from sifu.utils import SKILLS_ROOT

# sifu's own references hold the rules every audit applies.
REFERENCES_DIR = SKILLS_ROOT / "home" / "sifu" / "references"

CODE_RE = re.compile(r"^\*\*Code:\*\* ([A-Z]{3})\s*$")
APPLIES_RE = re.compile(r"^\*\*Applies:\*\* (.+?)\s*$")
SECTION_RE = re.compile(r"^## (\d+)\. ")
ITEM_RE = re.compile(r"^(\d+)\.\s+(.*)$")
ANNOTATION_RE = re.compile(
    r"^\(rule: ([A-Z]{3})-(\d+)-(\d+), severity: (\d{1,3})\)\s*(.*)$")
# Back-pointer to the lint function that already enforces a rule.
AUTOCHECK_RE = re.compile(r"\(check:\s*`?autochecks/([\w.]+:\w+)`?\)")
# First RFC 2119 keyword outside backticks/parentheses decides the base.
KEYWORD_RE = re.compile(
    r"\b(MUST NOT|SHALL NOT|MUST|SHALL|SHOULD NOT|SHOULD|NOT REQUIRED|MAY)\b")
KEYWORD_CANON = {
    "MUST NOT": "MUST NOT", "SHALL NOT": "MUST NOT",
    "MUST": "MUST", "SHALL": "MUST",
    "SHOULD NOT": "SHOULD", "SHOULD": "SHOULD",
    "NOT REQUIRED": "MAY", "MAY": "MAY",
}
# Keyword base and its reachable range (base .. base + 30 safety impact).
KEYWORD_BASE = {"MUST NOT": 70, "MUST": 65, "SHOULD": 45, "MAY": 20,
                "none": 10}
# Review bands (rule-codes.md §3). Below INFO is not sharded.
ERROR_MIN = 90
WARNING_MIN = 70
INFO_MIN = 50
# Severity axis is 0-100 (rule-codes.md §2).
SEVERITY_MAX = 100
# Impact classes add at most 30 (safety) to the keyword base.
IMPACT_MAX = 30


def band(severity: int) -> str:
    """Error / Warning / Info / "" (below review threshold)."""
    if severity >= ERROR_MIN:
        return "Error"
    if severity >= WARNING_MIN:
        return "Warning"
    if severity >= INFO_MIN:
        return "Info"
    return ""


def _strip_inline(text: str) -> str:
    """Drop backtick spans and parentheticals so quoted keywords (e.g.
    "(MUST, SHOULD, MAY)") do not decide the base."""
    text = re.sub(r"`[^`]*`", "", text)
    return re.sub(r"\([^)]*\)", "", text)


def keyword_of(text: str) -> str:
    m = KEYWORD_RE.search(_strip_inline(text))
    return KEYWORD_CANON[m.group(1)] if m else "none"


def _items(lines: list[str]):
    """Yield (line_no, section, item_no, first_line, body) for every
    numbered list item under a numbered H2, skipping fenced blocks.
    ``body`` joins the item's first paragraph (continuation lines)."""
    section = 0
    in_fence = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            in_fence = not in_fence
            i += 1
            continue
        if in_fence:
            i += 1
            continue
        m = SECTION_RE.match(line)
        if m:
            section = int(m.group(1))
            i += 1
            continue
        m = ITEM_RE.match(line)
        if m and section:
            first = m.group(2)
            parts = [first]
            j = i + 1
            while (j < len(lines) and lines[j].strip()
                   and lines[j].startswith("   ")):
                parts.append(lines[j].strip())
                j += 1
            yield i + 1, section, int(m.group(1)), first, " ".join(parts)
            i = j
            continue
        i += 1


def parse_file(path: Path, rel: str) -> dict:
    """Return {code, applies, checks, problems} for one reference.

    ``problems`` lists grammar violations as (line, message) so the
    rule_codes lint and this parser share one reading of the file.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    code = ""
    applies: list[str] = []
    problems: list[tuple[int, str]] = []
    for n, line in enumerate(lines[:6], start=1):
        m = CODE_RE.match(line)
        if m:
            code = m.group(1)
        m = APPLIES_RE.match(line)
        if m:
            applies = [t.strip() for t in m.group(1).split(",") if t.strip()]
    checks: list[dict] = []
    for line_no, section, item, first, body in _items(lines):
        m = ANNOTATION_RE.match(first)
        if not m:
            problems.append((line_no, f"rule {section}.{item} lacks a "
                             "(rule: CODE-s-r, severity: n) annotation"))
            continue
        a_code, a_sec, a_item, sev, _rest = m.groups()
        rule_id = f"{a_code}-{a_sec}-{a_item}"
        if code and a_code != code:
            problems.append((line_no, f"{rule_id}: file code is {code}"))
        if int(a_sec) != section or int(a_item) != item:
            problems.append((line_no, f"{rule_id}: rule sits at "
                             f"{section}.{item}"))
        text = ANNOTATION_RE.sub(r"\5", body, count=1)
        text = AUTOCHECK_RE.sub("", text).strip()
        kw = keyword_of(text)
        severity = int(sev)
        low = KEYWORD_BASE[kw]
        if not low <= severity <= min(low + IMPACT_MAX, SEVERITY_MAX):
            problems.append((line_no, f"{rule_id}: severity {severity} "
                             f"outside {kw} range {low}-{low + IMPACT_MAX}"))
        ac = AUTOCHECK_RE.search(body)
        checks.append({
            "id": rule_id, "file": rel, "code": a_code,
            "section": section, "rule": item, "text": text,
            "keyword": kw, "severity": severity,
            "autocheck": ac.group(1) if ac else "",
        })
    if not code:
        problems.insert(0, (1, "missing **Code:** header"))
    return {"code": code, "applies": applies, "checks": checks,
            "problems": problems, "path": path}


def rule_files(refs_dir: Path = REFERENCES_DIR) -> list[dict]:
    """Every reference that declares a **Code:** header, in name order."""
    parsed = [parse_file(p, f"references/{p.name}")
              for p in sorted(refs_dir.glob("*.md"))]
    return [r for r in parsed if r["code"]]


def load_checks(refs_dir: Path = REFERENCES_DIR) -> list[dict]:
    return [c for r in rule_files(refs_dir) for c in r["checks"]]


def severity_of(rule_id: str, refs_dir: Path = REFERENCES_DIR) -> int:
    for c in load_checks(refs_dir):
        if c["id"] == rule_id:
            return c["severity"]
    raise KeyError(f"unknown rule id {rule_id}")


def select(refs: list[dict], topics: list[str], min_severity: int = INFO_MIN,
           drop_autochecked: bool = True) -> list[dict]:
    """Checks of the references whose Applies meets ``topics`` (or
    ``always``), at or above ``min_severity``, ordered severity-desc
    within each file."""
    wanted = set(topics)
    out: list[dict] = []
    for r in refs:
        if "always" not in r["applies"] and not wanted & set(r["applies"]):
            continue
        keep = [c for c in r["checks"]
                if c["severity"] >= min_severity
                and not (drop_autochecked and c["autocheck"])]
        keep.sort(key=lambda c: (-c["severity"], c["section"], c["rule"]))
        out.extend(keep)
    return out

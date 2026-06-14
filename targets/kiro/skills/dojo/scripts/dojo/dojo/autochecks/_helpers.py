"""Shared types, parsers, and constants for the dojo autochecks package.

Per-rule check modules (authoring.py, script_conventions.py, etc.)
import from this module. The orchestrator in checks.py composes
all rule modules into ``lint_skill``.
"""

from __future__ import annotations

import re
from functools import wraps
from typing import Callable, List, NamedTuple, Tuple

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class Finding(NamedTuple):
    """One automated finding.

    ``rule`` is the check function name (e.g. ``rule_2_2_activity_pattern``)
    and ``rule_ref`` is the markdown source location of the rule
    (e.g. ``references/workflow-conventions.md:31``). Both fields default
    to empty for SKIP advisories and frontmatter parser errors that have
    no single backing rule.
    """
    severity: str
    filename: str
    line: int                # 0 = whole-file
    message: str
    rule: str = ""
    rule_ref: str = ""


ERROR = "ERROR"
WARN = "WARN"
SKIP = "SKIP"
INFO = "INFO"


# ---------------------------------------------------------------------------
# Rule decorator
# ---------------------------------------------------------------------------


def rule(ref: str) -> Callable:
    """Tag every Finding returned by a rule function with the rule's
    name (function ``__name__``) and ``ref`` (markdown source link).

    Usage:
        @rule("references/authoring.md:69")
        def rule_3_2_name_format(fields): ...
    """

    def decorator(func: Callable[..., List[Finding]]) -> Callable[..., List[Finding]]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> List[Finding]:
            findings = func(*args, **kwargs)
            out: List[Finding] = []
            for f in findings:
                # Promote plain tuples (legacy callers) to Finding.
                if not isinstance(f, Finding):
                    f = Finding(*f)
                out.append(f._replace(rule=func.__name__, rule_ref=ref))
            return out

        return wrapper

    return decorator


def to_finding(f) -> Finding:
    """Promote a raw tuple to a Finding (no-op if already a Finding)."""
    if isinstance(f, Finding):
        return f
    return Finding(*f)

# ---------------------------------------------------------------------------
# Constants used by multiple rule modules
# ---------------------------------------------------------------------------

# Valid skill types per authoring.md §3.3.
VALID_TYPES = {"interface", "tool", "workflow", "reference"}

# Trigger keywords that should appear in `description` so the
# router can match user intent — authoring.md §3.4.
TRIGGER_PATTERNS = [
    re.compile(r"Use when", re.IGNORECASE),
    re.compile(r"MUST load when", re.IGNORECASE),
    re.compile(r'"[^"]+"'),  # quoted trigger phrase
]

# Pattern for Amazon-style aliases: @ followed by login-shaped text.
ALIAS_PATTERN = re.compile(r"@[a-z]{2,}[a-z0-9]{0,}")

# 75 chars: prose minimum-fill threshold per authoring.md §5.8.
MIN_PROSE_FILL = 75


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(lines: List[str]) -> Tuple[dict, List[Finding]]:
    """Parse YAML frontmatter delimited by '---' lines.

    Returns ``(fields, findings)`` where fields maps field name →
    ``(value, line_number)`` and findings contains parser errors,
    including violations of the single-line rule
    (authoring.md §3.6).
    """
    findings: List[Finding] = []
    fields: dict = {}

    if not lines or lines[0].rstrip() != "---":
        findings.append(
            (ERROR, "SKILL.md", 1,
             "Missing opening frontmatter delimiter '---'")
        )
        return fields, findings

    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close_idx = i
            break

    if close_idx is None:
        findings.append(
            (ERROR, "SKILL.md", 1,
             "Missing closing frontmatter delimiter '---'")
        )
        return fields, findings

    for i in range(1, close_idx):
        line = lines[i]
        lineno = i + 1

        # YAML folding violates authoring.md §3.6 (single-line fields).
        if line.rstrip().endswith(">") or line.rstrip().endswith("|"):
            findings.append(
                (ERROR, "SKILL.md", lineno,
                 "Frontmatter uses YAML folding — fields must be "
                 "single lines")
            )
            continue

        # Continuation lines also violate §3.6.
        if line.startswith(" ") and ":" not in line.split("#")[0]:
            findings.append(
                (ERROR, "SKILL.md", lineno,
                 "Frontmatter continuation line — fields must be "
                 "single lines")
            )
            continue

        match = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if match:
            fields[match.group(1)] = (match.group(2).strip(), lineno)
        else:
            findings.append(
                (WARN, "SKILL.md", lineno,
                 f"Unrecognized frontmatter line: {line.rstrip()}")
            )

    return fields, findings


# ---------------------------------------------------------------------------
# Heading extraction
# ---------------------------------------------------------------------------

def get_headings(
    lines: List[str],
) -> List[Tuple[int, int, str]]:
    """Extract ATX-style markdown headings as ``(line_no, level, text)``.

    Skips headings inside fenced code blocks.
    """
    headings: List[Tuple[int, int, str]] = []
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            headings.append((i + 1, len(m.group(1)), m.group(2).strip()))
    return headings


# ---------------------------------------------------------------------------
# Prose detection (used by the line-width rule)
# ---------------------------------------------------------------------------

def is_prose(stripped: str) -> bool:
    """Return True if a stripped line is prose, not a structural line."""
    if not stripped:
        return False
    if stripped.startswith(("#", "|", "-", "*", "`", "  ", ">")):
        return False
    if re.match(r"^\d+\.\s", stripped):
        return False
    return True

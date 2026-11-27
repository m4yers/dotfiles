"""Automated checks for ``references/tool-conventions.md``."""

from __future__ import annotations

import re
from typing import List, Tuple

from sifu.autochecks._helpers import Finding, rule


@rule('TOL-2-1')
def rule_2_1_steps_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Tool skills MUST have a ``## Steps`` section.

    Rule: TOL-2-1
    """
    findings: List[Finding] = []
    h2_names = [h[2].lower() for h in headings if h[1] == 2]
    if "steps" not in h2_names:
        findings.append(
            ("SKILL.md", 0,
             "tool skill missing required '## Steps' section")
        )
    return findings


@rule('TOL-2-2')
def rule_2_2_parameters_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Tool skills MUST have a ``## Parameters`` section.

    Rule: TOL-2-2
    """
    findings: List[Finding] = []
    h2_names = [h[2].lower() for h in headings if h[1] == 2]
    if "parameters" not in h2_names:
        findings.append(
            ("SKILL.md", 0,
             "tool skill missing required '## Parameters' section")
        )
    return findings


@rule('TOL-3-2')
def rule_3_2_steps_numbered(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Steps in a tool skill MUST be numbered list items, not
    bulleted.

    Rule: TOL-3-2
    """
    findings: List[Finding] = []
    steps_start = None
    steps_end = len(lines)
    for ph_lineno, level, text in headings:
        if level == 2 and text.lower() == "steps":
            steps_start = ph_lineno
        elif steps_start is not None and level == 2:
            steps_end = ph_lineno - 1
            break
    if steps_start is None:
        return findings
    in_code = False
    for i in range(steps_start, steps_end):
        if i >= len(lines):
            break
        line = lines[i]
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        # Top-level bullet at indent 0 is the violation. Indented
        # bullets inside numbered items are continuation.
        if re.match(r"^[-*]\s+", line):
            findings.append(
                ("SKILL.md", i + 1,
                 "step uses '-' bullet — tool steps MUST be "
                 "numbered, not bulleted")
            )
    return findings


@rule('TOL-5-4')
def rule_5_no_api_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Tool skills MUST NOT have an ``## API`` section
    (that is an interface).

    Rule: TOL-5-4
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    if "api" in h2_names:
        findings.append(
            ("SKILL.md", 0,
             "tool skill must not have '## API' section "
             "— that is an `interface`")
        )
    return findings

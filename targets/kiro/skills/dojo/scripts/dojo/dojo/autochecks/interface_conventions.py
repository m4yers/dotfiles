"""Automated checks for ``references/interface-conventions.md``."""

from __future__ import annotations

from typing import List, Tuple

from dojo.autochecks._helpers import ERROR, Finding, rule

@rule('references/interface-conventions.md:2.1')
def rule_2_1_invocation_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Interface skills MUST have an ``## Invocation`` section.

    Rule: references/interface-conventions.md:2.1
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    if "invocation" not in h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "interface skill missing required '## Invocation' section")
        )
    return findings


@rule('references/interface-conventions.md:2.2')
def rule_2_2_api_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Interface skills MUST have an ``## API`` section.

    Rule: references/interface-conventions.md:2.2
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    if "api" not in h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "interface skill missing required '## API' section")
        )
    return findings


@rule('references/interface-conventions.md:2.3')
def rule_2_3_commands_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Interface skills MUST have a ``## Commands`` section.

    Rule: references/interface-conventions.md:2.3
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    if "commands" not in h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "interface skill missing required '## Commands' section")
        )
    return findings


@rule('references/interface-conventions.md:2.4')
def rule_2_4_api_commands_match(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Every entry in the API table MUST have a matching
    ``### <command>`` subsection in Commands.

    Rule: references/interface-conventions.md:2.4
    """
    import re

    findings: List[Finding] = []

    api_start = api_end = None
    cmds_start = cmds_end = len(lines)
    for ph_lineno, level, text in headings:
        if level == 2 and text.lower() == "api":
            api_start = ph_lineno
        elif level == 2 and text.lower() == "commands":
            cmds_start = ph_lineno
            if api_start is not None and api_end is None:
                api_end = ph_lineno - 1
        elif level == 2 and cmds_start != len(lines):
            cmds_end = ph_lineno - 1
            break

    if api_start is None:
        return findings
    if api_end is None:
        api_end = cmds_start - 1

    # Pull the first column out of every API table row.
    api_cmds: list[str] = []
    in_code = False
    for i in range(api_start, min(api_end, len(lines))):
        line = lines[i]
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not line.strip().startswith("|"):
            continue
        # Skip header separator rows like '|---|---|'.
        if re.match(r"^\s*\|[\s|:-]+\|\s*$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        # Header row check: first cell is "Command" or empty.
        if first.lower() in ("command", "cmd", ""):
            continue
        # Strip backticks from first cell to get the command name.
        cmd = first.strip("`")
        if cmd:
            api_cmds.append(cmd)

    # Collect ### subsection titles within Commands section.
    h3_titles: list[str] = []
    for ph_lineno, level, text in headings:
        if level == 3 and cmds_start <= ph_lineno <= cmds_end:
            h3_titles.append(text)

    for cmd in api_cmds:
        # Match if any h3 contains the command name as a token.
        if not any(
            cmd == h or cmd in h.split()
            for h in h3_titles
        ):
            findings.append(
                (WARN, "SKILL.md", api_start,
                 f"API command '{cmd}' has no matching "
                 f"### subsection in Commands")
            )
    return findings

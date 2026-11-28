"""Automated checks for ``references/reference-conventions.md``."""

from __future__ import annotations

from typing import List, Tuple

from sifu.autochecks._helpers import Finding, rule

@rule('REF-4-3')
def rule_4_3_file_length(
    ref_lines: List[str], filename: str,
) -> List[Finding]:
    """Reference files SHOULD be under 300 lines.

    Rule: REF-4-3
    """
    findings: List[Finding] = []
    if len(ref_lines) > 300:
        findings.append(
            (filename, 0,
             f"reference file is {len(ref_lines)} lines "
             f"(recommended max 300)")
        )
    return findings


@rule('REF-5-1')
def rule_5_1_no_procedures(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Reference skills MUST NOT contain procedures or workflows.

    Rule: REF-5-1
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    for section in sorted({"steps", "workflow"} & h2_names):
        findings.append(
            ("SKILL.md", 0,
             f"reference skill must not have '## {section.title()}' "
             f"section — references are passive rule sets")
        )
    return findings


@rule('REF-5-2')
def rule_5_2_no_script_apis(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Reference skills MUST NOT contain script APIs.

    Rule: REF-5-2
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    if "commands" in h2_names:
        findings.append(
            ("SKILL.md", 0,
             "reference skill must not have '## Commands' "
             "section — references are passive rule sets")
        )
    return findings


@rule('REF-5-3')
def rule_5_3_no_invocation_api(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Reference skills MUST NOT contain Invocation or API sections.

    Rule: REF-5-3
    """
    findings: List[Finding] = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    for section in sorted({"invocation", "api"} & h2_names):
        findings.append(
            ("SKILL.md", 0,
             f"reference skill must not have '## {section.title()}' "
             f"section — references are passive rule sets")
        )
    return findings


@rule('REF-2-1')
def rule_2_1_must_load_when(fields: dict) -> List[Finding]:
    """Reference-skill ``description`` MUST contain "MUST load when"
    or "MUST load whenever" phrasing — this is the only invocation
    a reference has.

    Rule: REF-2-1
    """
    findings: List[Finding] = []
    if fields.get("type", ("",))[0] != "reference":
        return findings
    if "description" not in fields:
        return findings
    desc, lineno = fields["description"]
    if "MUST load when" not in desc:
        findings.append(
            ("SKILL.md", lineno,
             "reference-skill description should contain "
             "'MUST load when' phrasing — this is the only "
             "invocation a reference has")
        )
    return findings

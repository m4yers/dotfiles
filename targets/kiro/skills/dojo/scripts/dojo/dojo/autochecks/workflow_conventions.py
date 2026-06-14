"""Automated checks for ``references/workflow-conventions.md``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

from dojo.autochecks._helpers import ERROR, Finding, WARN, rule

@rule('references/workflow-conventions.md:31')
def rule_2_2_activity_pattern(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Each step MUST start with ``activity set`` containing a target.

    The template enforces the pattern; this rule lints hand-edited
    SKILL.md files for conformance.

    Rule: references/workflow-conventions.md:31
    """
    findings: List[Finding] = []
    step_headings = [
        h for h in headings
        if h[1] == 3 and re.match(r"^(Step\s+)?\d+", h[2])
    ]
    for ph_lineno, _, ph_text in step_headings:
        found_activity = False
        has_target = False
        search_end = min(ph_lineno + 15, len(lines))
        for j in range(ph_lineno, search_end):
            if "activity set" in lines[j]:
                found_activity = True
                if re.search(
                    r'activity set "[^"]*\([^)]+\)', lines[j],
                ):
                    has_target = True
                break
            if (j > ph_lineno
                    and lines[j].strip().startswith("#")):
                break
        if not found_activity:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' does not start with "
                 f"tiling activity set")
            )
        elif not has_target:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' activity label missing "
                 f"target — use \"skill(<target>): Step\"")
            )
    return findings


@rule('references/workflow-conventions.md:138')
def rule_8_2_max_substeps(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Each step MUST have at most 5 numbered sub-steps.

    Rule: references/workflow-conventions.md:138
    """
    findings: List[Finding] = []
    step_headings = [
        h for h in headings
        if h[1] == 3 and re.match(r"^(Step\s+)?\d+", h[2])
    ]
    for idx, (ph_lineno, _, ph_text) in enumerate(step_headings):
        if idx + 1 < len(step_headings):
            step_end = step_headings[idx + 1][0] - 1
        else:
            step_end = len(lines)
        substep_count = 0
        in_code = False
        for j in range(ph_lineno, step_end):
            ln = lines[j]
            if ln.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if ln.strip().startswith("## "):
                break
            if re.match(r"^\d+\.\s", ln):
                substep_count += 1
        if substep_count > 5:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' has {substep_count} "
                 f"sub-steps (max 5)")
            )
    return findings


@rule('references/workflow-conventions.md:58')
def rule_4_1_name_alignment(skill_dir: Path) -> List[Finding]:
    """A task and its bound resources MUST share the same base
    name (task `<name>` ↔ `schemas/<name>.yaml` ↔
    `templates/prompts/<name>.md.j2`).

    Approximated statically by pairing prompt files under
    ``templates/prompts/`` with schema files under ``schemas/``:
    every prompt MUST have a same-named schema. Findings are
    warnings (the rule may be overridden by intentionally shared
    schemas — see §4.4).

    Rule: references/workflow-conventions.md:58
    """
    findings: List[Finding] = []
    prompts_dir = skill_dir / "templates" / "prompts"
    schemas_dir = skill_dir / "schemas"
    if not prompts_dir.is_dir() or not schemas_dir.is_dir():
        return findings

    schema_names = {
        p.stem for p in schemas_dir.glob("*.yaml")
    }
    for prompt in sorted(prompts_dir.glob("*.md.j2")):
        # Strip the trailing ".md" to get the task base name.
        base = prompt.name[:-len(".md.j2")]
        if base not in schema_names:
            findings.append(
                (WARN, f"templates/prompts/{prompt.name}", 0,
                 f"prompt '{base}' has no matching "
                 f"schema 'schemas/{base}.yaml' — task and "
                 f"its bound schema/prompt MUST share a name")
            )
    return findings


@rule('references/workflow-conventions.md:135')
def rule_8_1_descriptive_step_name(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Each step MUST have a descriptive name after the number
    (e.g., "Step 1: Setup & Checkout"), not just "Step 1".

    Rule: references/workflow-conventions.md:135
    """
    findings: List[Finding] = []
    step_re = re.compile(r"^(?:Step\s+)?(\d+)(?::\s*(.+))?\s*$")
    for ph_lineno, level, text in headings:
        if level != 3:
            continue
        m = step_re.match(text)
        if not m:
            continue
        name = (m.group(2) or "").strip()
        if not name:
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step heading '{text}' has no descriptive name "
                 f"after the number")
            )
    return findings

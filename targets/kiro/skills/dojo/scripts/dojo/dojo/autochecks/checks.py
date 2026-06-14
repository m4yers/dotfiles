"""Lint orchestrator — composes per-reference rule modules.

Per-rule check implementations live in sibling modules
(``authoring.py``, ``script_conventions.py``, etc.). Each rule
function is named ``rule_<section>_<rule>_<blurb>`` and carries a
``Rule:`` reference to the markdown file it enforces. This module
runs every rule against a skill directory and aggregates findings.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from dojo.autochecks import (
    authoring,
    interface_conventions,
    reference_conventions,
    script_conventions,
    tool_conventions,
    workflow_conventions,
)
from dojo.autochecks._helpers import (
    ERROR, Finding, INFO, SKIP, WARN,
    get_headings, parse_frontmatter, to_finding,
)

# Re-exports for backwards compatibility.
__all__ = [
    "ERROR", "INFO", "SKIP", "WARN",
    "Finding", "lint_skill",
    "lint_to_findings", "lint_to_text",
]


# ---------------------------------------------------------------------------
# Output adapters
# ---------------------------------------------------------------------------

# Internal severity → findings.yaml schema enum. SKIP is dropped
# from emission — those are LLM-checked advisories, not lint
# violations.
_SEVERITY_MAP = {
    ERROR: "Error",
    WARN:  "Warning",
    INFO:  "Info",
}


def lint_to_findings(skill_dir: Path) -> list[dict]:
    """Run autochecks and return findings as ``findings.yaml`` dicts.

    SKIP findings are excluded — advisory, not actionable.
    """
    out: list[dict] = []
    for f in lint_skill(skill_dir):
        if f.severity == SKIP:
            continue
        loc = f"{f.filename}:{f.line}" if f.line > 0 else f.filename
        entry = {
            "title": f.message[:80],
            "file_line": loc,
            "description": f.message,
            "fix": "Address per dojo conventions.",
            "severity": _SEVERITY_MAP[f.severity],
            "source": "autochecks",
        }
        if f.rule:
            entry["rule_fun"] = f.rule
        if f.rule_ref:
            entry["rule_ref"] = f.rule_ref
        out.append(entry)
    return out


def lint_to_text(skill_dir: Path) -> str:
    """Render autocheck findings as legacy human-readable text.

    Used by ``--format text`` and the apply phase to verify fixes.
    """
    counts = {ERROR: 0, WARN: 0, SKIP: 0, INFO: 0}
    lines: list[str] = []
    for f in lint_skill(skill_dir):
        counts[f.severity] += 1
        loc = f"{f.filename}:{f.line}" if f.line > 0 else f.filename
        rule_tag = f"  [{f.rule}]" if f.rule else ""
        lines.append(f"  {f.severity:5s}  {loc:30s}  {f.message}{rule_tag}")
    lines.append("")
    lines.append(
        f"Summary: {counts[ERROR]} errors, {counts[WARN]} warnings, "
        f"{counts[SKIP]} skipped (manual), {counts[INFO]} info"
    )
    return "\n".join(lines) + "\n"


def lint_skill(skill_dir: Path) -> List[Finding]:
    """Run every automated rule check on a skill directory.

    Each rule lives in its reference module (``authoring.py`` etc.)
    and has a docstring pointing at ``references/<file>.md:<line>``.
    """
    findings: List[Finding] = []
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        findings.append((ERROR, "SKILL.md", 0, "SKILL.md not found"))
        return findings

    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Frontmatter (also checks §3.6 single-line rule via parser).
    fields, fm_findings = parse_frontmatter(lines)
    findings.extend(fm_findings)

    # authoring.md §3 Frontmatter.
    findings.extend(authoring.rule_3_2_name_format(fields))
    findings.extend(authoring.rule_3_3_type_values(fields))
    findings.extend(authoring.rule_3_4_description_length(fields))
    findings.extend(authoring.rule_3_5_description_person(fields))

    # authoring.md §1 Directory Structure.
    findings.extend(authoring.rule_1_3_md_under_references(skill_dir))
    findings.extend(authoring.rule_1_4_schemas_top_level(skill_dir))
    findings.extend(authoring.rule_1_6_scripts_directory(skill_dir))
    findings.extend(authoring.rule_5_16_no_orphans(skill_dir))

    # authoring.md §5 Style Guide (applied to SKILL.md).
    findings.extend(authoring.rule_5_3_no_readme(skill_dir))
    findings.extend(authoring.rule_5_4_constraints_form(lines, "SKILL.md"))
    findings.extend(authoring.rule_5_8_line_widths(lines, "SKILL.md"))
    findings.extend(authoring.rule_5_10_emphasis_stacking(lines, "SKILL.md"))

    # authoring.md §6 Completion Status.
    findings.extend(authoring.rule_6_1_completion_section(lines))
    findings.extend(authoring.rule_6_2_completion_statuses(lines))

    # authoring.md §7 Handle Policy.
    findings.extend(authoring.rule_7_1_no_other_aliases(lines, "SKILL.md"))

    # script-conventions.md.
    findings.extend(
        script_conventions.rule_3_1_named_aliases(lines, "SKILL.md")
    )
    findings.extend(
        script_conventions.rule_3_2_unique_aliases(lines, "SKILL.md")
    )
    findings.extend(
        script_conventions.rule_4_2_bash_size_limit(skill_dir)
    )
    findings.extend(
        script_conventions.rule_5_2_pyproject_per_package(skill_dir)
    )

    # Type-specific structure (interface / tool / workflow / reference).
    headings = get_headings(lines)
    if "type" in fields:
        skill_type = fields["type"][0]
        if skill_type == "interface":
            findings.extend(
                interface_conventions.rule_2_1_invocation_section(headings)
            )
            findings.extend(
                interface_conventions.rule_2_2_api_section(headings)
            )
            findings.extend(
                interface_conventions.rule_2_3_commands_section(headings)
            )
            findings.extend(
                interface_conventions.rule_2_4_api_commands_match(
                    lines, headings,
                )
            )
        elif skill_type == "tool":
            findings.extend(
                tool_conventions.rule_2_1_steps_section(headings)
            )
            findings.extend(
                tool_conventions.rule_2_2_parameters_section(headings)
            )
            findings.extend(
                tool_conventions.rule_3_2_steps_numbered(lines, headings)
            )
            findings.extend(
                tool_conventions.rule_5_no_api_section(headings)
            )
        elif skill_type == "workflow":
            findings.extend(
                workflow_conventions.rule_2_2_activity_pattern(
                    lines, headings,
                )
            )
            findings.extend(
                workflow_conventions.rule_8_1_descriptive_step_name(
                    headings,
                )
            )
            findings.extend(
                workflow_conventions.rule_8_2_max_substeps(
                    lines, headings,
                )
            )
            findings.extend(
                workflow_conventions.rule_4_1_name_alignment(skill_dir)
            )
        elif skill_type == "reference":
            findings.extend(
                reference_conventions.rule_2_1_must_load_when(fields)
            )
            findings.extend(
                reference_conventions.rule_5_1_no_procedures(headings)
            )
            findings.extend(
                reference_conventions.rule_5_2_no_script_apis(headings)
            )
            findings.extend(
                reference_conventions.rule_5_3_no_invocation_api(headings)
            )

    # Per-reference-file checks.
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref_file in sorted(refs_dir.iterdir()):
            if ref_file.suffix != ".md":
                continue
            ref_text = ref_file.read_text(encoding="utf-8")
            ref_lines = ref_text.splitlines()
            ref_name = f"references/{ref_file.name}"

            findings.extend(
                reference_conventions.rule_4_4_file_length(
                    ref_lines, ref_name,
                )
            )
            findings.extend(
                authoring.rule_5_14_toc_long_files(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_5_8_line_widths(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_5_4_constraints_form(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_5_10_emphasis_stacking(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_7_1_no_other_aliases(ref_lines, ref_name)
            )
            findings.extend(
                script_conventions.rule_3_1_named_aliases(
                    ref_lines, ref_name,
                )
            )

        findings.extend(
            authoring.rule_5_13_references_reachable(skill_dir, refs_dir)
        )

    # Skipped (semantic) checks — surfaced as SKIP advisories.
    skipped = [
        "Trigger phrase uniqueness across skills",
        "Functionality uniqueness across skills",
        "Negative trigger phrase coverage",
        "Reference file focus (one topic each)",
        "Repeatable actions (deterministic actions as scripts)",
        "Missing oracles (steps with verifiable outcomes need automated oracle sub-steps)",
        "Positive framing (MUST NOT vs positive alternative)",
        "Magic constants in scripts (uncommented values)",
        "Gameable success criteria (measurable outcomes have anti-gaming guards)",
        "Reinvention in scripts (reimplements stdlib/Linux tools)",
    ]
    for desc in skipped:
        findings.append((SKIP, "SKILL.md", 0, desc))

    # Normalize: promote any plain tuples (parser errors, SKIP) to Finding.
    findings = [to_finding(f) for f in findings]
    findings.sort(key=lambda f: (f.filename, f.line))
    return findings

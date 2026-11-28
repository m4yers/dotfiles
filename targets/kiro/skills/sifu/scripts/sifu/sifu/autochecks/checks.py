"""Lint orchestrator — composes per-reference rule modules.

Per-rule check implementations live in sibling modules
(``authoring.py``, ``script_conventions.py``, etc.). Each rule
function is named ``rule_<section>_<rule>_<blurb>`` and carries a
``Rule:`` reference to the markdown file it enforces. This module
runs every rule against a skill directory and aggregates findings.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from sifu import rules
from sifu.autochecks import (
    authoring,
    flow_conventions,
    interface_conventions,
    reference_conventions,
    rule_codes,
    script_conventions,
    tool_conventions,
    workflow_conventions,
)
from sifu.autochecks._helpers import (
    Finding, get_headings, parse_frontmatter, to_finding,
)
from sifu.utils import SKILLS_ROOT

__all__ = ["Finding", "lint_skill", "lint_to_findings", "lint_to_text"]


# ---------------------------------------------------------------------------
# Output adapters
# ---------------------------------------------------------------------------

# Deterministic findings are certain by construction (rule-codes.md §3).
_LINT_CONFIDENCE = 100


def lint_to_findings(skill_dir: Path) -> list[dict]:
    """Run autochecks and return findings as ``finding.yaml`` dicts."""
    out: list[dict] = []
    for f in lint_skill(skill_dir):
        loc = f"{f.filename}:{f.line}" if f.line > 0 else f.filename
        entry = {
            # 80 — findings title cap used by the check prompts and the
            # report's one-line headings.
            "title": f.message[:80],
            "file_line": loc,
            "description": f.message,
            "fix": "Address per sifu conventions.",
            "check_id": f.code,
            "severity": rules.severity_of(f.code),
            "confidence": _LINT_CONFIDENCE,
            "source": "autochecks",
        }
        if f.rule:
            entry["rule_fun"] = f.rule
        out.append(entry)
    return out


def lint_to_text(skill_dir: Path) -> str:
    """Render autocheck findings as human-readable text.

    Used by ``--format text`` and the apply phase to verify fixes.
    """
    counts = {"Error": 0, "Warning": 0, "Info": 0, "": 0}
    lines: list[str] = []
    for f in lint_to_findings(skill_dir):
        band = rules.band(f["severity"])
        counts[band] += 1
        rule_tag = f"  [{f['rule_fun']}]" if f.get("rule_fun") else ""
        lines.append(f"  {band or 'below':7s} {f['check_id']:9s} "
                     f"{f['file_line']:30s}  {f['description']}{rule_tag}")
    lines.append("")
    lines.append(
        f"Summary: {counts['Error']} errors, {counts['Warning']} warnings, "
        f"{counts['Info']} info"
    )
    return "\n".join(lines) + "\n"


# Style rules whose hits inside loomv2 host partials are not the skill's
# to fix: the partial text is owned by loomv2 (workflow-conventions §2.1).
_PARTIAL_EXEMPT_RULES = {
    "rule_5_4_constraints_form", "rule_5_7_line_widths",
    "rule_5_9_emphasis_stacking", "rule_7_1_no_other_aliases",
}
LOOMV2_TEMPLATES = SKILLS_ROOT / "home" / "loomv2" / "templates"
# 20 chars: partial lines shorter than this (fences, headings like
# "## Task", bare list markers) also occur in skill-authored text, so
# matching them would hide the skill's own findings.
_MIN_PARTIAL_LINE = 20
_JINJA_EXPR = re.compile(r"\\\{\\\{.*?\\\}\\\}")


def _partial_line_patterns() -> List["re.Pattern[str]"]:
    """One regex per non-trivial loomv2 partial line, with every
    ``{{ expr }}`` turned into a wildcard."""
    pats = []
    if not LOOMV2_TEMPLATES.is_dir():
        return pats
    for tpl in LOOMV2_TEMPLATES.glob("*.md.j2"):
        body = re.sub(r"\{#.*?#\}", "", tpl.read_text(encoding="utf-8"),
                      flags=re.S)
        for line in body.splitlines():
            if len(line.strip()) < _MIN_PARTIAL_LINE:
                continue
            pats.append(re.compile(
                "^" + _JINJA_EXPR.sub(".*?", re.escape(line.rstrip())) + "$"))
    return pats


def _drop_partial_noise(findings: List[Finding], lines: List[str]) -> List[Finding]:
    pats = _partial_line_patterns()
    if not pats:
        return findings
    out = []
    for f in findings:
        if (f.filename == "SKILL.md" and f.rule in _PARTIAL_EXEMPT_RULES
                and 0 < f.line <= len(lines)
                and any(p.match(lines[f.line - 1].rstrip()) for p in pats)):
            continue
        out.append(f)
    return out


def lint_skill(skill_dir: Path) -> List[Finding]:
    """Run every automated rule check on a skill directory.

    Each rule lives in its reference module (``authoring.py`` etc.)
    and has a docstring pointing at ``references/<file>.md:<line>``.
    """
    findings: List[Finding] = []
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        return [Finding("SKILL.md", 0, "SKILL.md not found", code="AUT-1-2")]

    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Frontmatter (also checks §3.6 single-line rule via parser).
    fields, fm_findings = parse_frontmatter(lines)
    findings.extend(to_finding(f)._replace(code="AUT-3-6") for f in fm_findings)

    # authoring.md §3 Frontmatter.
    findings.extend(authoring.rule_3_2_name_format(fields))
    findings.extend(authoring.rule_3_3_type_values(fields))
    findings.extend(authoring.rule_3_4_description_length(fields))
    findings.extend(authoring.rule_3_5_description_person(fields))

    # authoring.md §1 Directory Structure.
    findings.extend(authoring.rule_1_3_md_under_references(skill_dir))
    findings.extend(authoring.rule_1_4_schemas_top_level(skill_dir))
    findings.extend(authoring.rule_1_6_scripts_directory(skill_dir))
    findings.extend(authoring.rule_5_15_no_orphans(skill_dir))

    # style.md §1 Style Guide (applied to SKILL.md).
    findings.extend(authoring.rule_5_3_no_readme(skill_dir))
    findings.extend(authoring.rule_5_4_constraints_form(lines, "SKILL.md"))
    findings.extend(authoring.rule_5_7_line_widths(lines, "SKILL.md"))
    findings.extend(authoring.rule_5_9_emphasis_stacking(lines, "SKILL.md"))

    # completion.md §1 Completion Status.
    findings.extend(authoring.rule_6_1_completion_section(lines))
    findings.extend(authoring.rule_6_2_completion_statuses(lines))

    # style.md §2 Handle Policy.
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

    # Type-specific structure (interface / tool / workflow / reference / flow).
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
                workflow_conventions.rule_3_1_loomv2_driver(skill_dir)
            )
            findings.extend(
                workflow_conventions.rule_3_4_graphs_validate(skill_dir)
            )
            findings.extend(
                workflow_conventions.rule_4_1_task_folder_alignment(
                    skill_dir,
                )
            )
        elif skill_type == "flow":
            findings.extend(
                flow_conventions.rule_2_2_workflow_section(headings)
            )
            findings.extend(
                flow_conventions.rule_2_3_invariants_section(headings)
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
                reference_conventions.rule_4_3_file_length(
                    ref_lines, ref_name,
                )
            )
            findings.extend(
                authoring.rule_5_13_toc_long_files(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_5_7_line_widths(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_5_4_constraints_form(ref_lines, ref_name)
            )
            findings.extend(
                authoring.rule_5_9_emphasis_stacking(ref_lines, ref_name)
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
            authoring.rule_5_12_references_reachable(skill_dir, refs_dir)
        )
        findings.extend(rule_codes.rule_1_1_file_code(refs_dir))
        findings.extend(rule_codes.rule_1_2_code_matches_position(refs_dir))
        findings.extend(rule_codes.rule_1_3_applies_header(refs_dir))
        findings.extend(rule_codes.rule_2_2_severity_in_range(refs_dir))

    # Normalize: promote any plain tuples (parser errors) to Finding.
    findings = [to_finding(f) for f in findings]
    findings = _drop_partial_noise(findings, lines)
    findings.sort(key=lambda f: (f.filename, f.line))
    return findings

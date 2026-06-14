"""Automated checks for ``references/script-conventions.md``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from dojo.autochecks._helpers import ERROR, Finding, WARN, rule

@rule('references/script-conventions.md:54')
def rule_3_2_unique_aliases(
    lines: List[str], filename: str,
) -> List[Finding]:
    """Each script-alias env var MUST be declared once per file.

    Rule: references/script-conventions.md:54
    """
    findings: List[Finding] = []
    in_code = False
    decl_pattern = re.compile(
        r"^\s*([A-Z][A-Z0-9_]*)=[\S]*"
        r"~/\.kiro/skills/[^\s`]*/scripts/"
    )
    seen: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue
        m = decl_pattern.match(line)
        if not m:
            continue
        name = m.group(1)
        if name in seen:
            findings.append(
                (WARN, filename, i + 1,
                 f"alias '{name}' declared again "
                 f"(first at line {seen[name]}); "
                 f"declare each alias once and reuse")
            )
        else:
            seen[name] = i + 1
    return findings


@rule('references/script-conventions.md:53')
def rule_3_1_named_aliases(
    lines: List[str], filename: str,
) -> List[Finding]:
    """Code-block script invocations MUST use named env vars, not
    hardcoded ``~/.kiro/skills/...`` paths.

    Rule: references/script-conventions.md:53
    """
    findings: List[Finding] = []
    in_code = False
    pattern = re.compile(r"~/\.kiro/skills/[^\s`]*/scripts/")
    decl_pattern = re.compile(r"^\s*[A-Z][A-Z0-9_]*=")
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue
        if not pattern.search(line):
            continue
        if decl_pattern.match(line):
            continue
        findings.append(
            (ERROR, filename, i + 1,
             "script invocation uses hardcoded "
             "~/.kiro/skills/...; declare a named alias "
             "(e.g. NAME=~/.kiro/skills/.../scripts/foo.sh) "
             "and call $NAME — see script-conventions.md "
             "§ Script Invocation Paths")
        )
    return findings


@rule('references/script-conventions.md:79')
def rule_4_2_bash_size_limit(skill_dir: Path) -> List[Finding]:
    """Bash scripts >10 code lines MUST be converted to Python.

    Rule: references/script-conventions.md:79
    """
    findings: List[Finding] = []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return findings
    for script in sorted(scripts_dir.iterdir()):
        if (not script.is_file()
                or script.suffix not in (".sh", ".bash")):
            continue
        text = script.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        # Skip shebang; count non-blank, non-comment lines.
        code_lines = [
            ln for ln in lines[1:]
            if ln.strip() and not ln.strip().startswith("#")
        ]
        if len(code_lines) > 10:
            findings.append(
                (WARN, f"scripts/{script.name}", 0,
                 f"bash script has {len(code_lines)} code lines "
                 f"(max 10) — convert to Python for better "
                 f"argument handling and maintainability")
            )
    return findings


@rule('references/script-conventions.md:99')
def rule_5_2_pyproject_per_package(skill_dir: Path) -> List[Finding]:
    """``pyproject.toml`` MUST live inside each dep-using package
    under ``scripts/``, not at the ``scripts/`` top level.

    Rule: references/script-conventions.md:99
    """
    findings: List[Finding] = []
    top_pp = skill_dir / "scripts" / "pyproject.toml"
    if top_pp.exists():
        findings.append(
            (ERROR, "scripts/pyproject.toml", 0,
             "pyproject.toml at scripts/ top level — move it "
             "into the dep-using package directory (one "
             "pyproject per package; see script-conventions.md "
             "§ Python Scripts)")
        )
    return findings

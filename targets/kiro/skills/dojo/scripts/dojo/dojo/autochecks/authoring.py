"""Automated checks for rules in ``references/authoring.md``.

Each function checks one numbered rule. Function name is
``rule_<section>_<rule>_<blurb>`` and the docstring carries a
``Rule:`` reference to ``references/authoring.md:<line>`` (vim
``gf``-friendly).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

from dojo.autochecks._helpers import (
    ALIAS_PATTERN, ERROR, Finding, MIN_PROSE_FILL, TRIGGER_PATTERNS, VALID_TYPES, WARN, is_prose, rule,
)

# ---------------------------------------------------------------------------
# §1 Directory Structure
# ---------------------------------------------------------------------------


@rule('references/authoring.md:33')
def rule_1_6_scripts_directory(skill_dir: Path) -> List[Finding]:
    """Scripts MUST live under ``scripts/``, not loose at skill root.

    Rule: references/authoring.md:33
    """
    findings: List[Finding] = []
    for f in skill_dir.iterdir():
        if (f.is_file() and f.suffix in (".py", ".sh", ".bash")
                and f.name != "SKILL.md"):
            findings.append(
                (ERROR, f.name, 0,
                 f"script '{f.name}' is in skill root — move to scripts/")
            )
    return findings


@rule('references/authoring.md:23')
def rule_1_3_md_under_references(skill_dir: Path) -> List[Finding]:
    """Reference docs SHOULD live under ``references/``.

    Rule: references/authoring.md:23
    """
    findings: List[Finding] = []
    for f in skill_dir.iterdir():
        if (f.is_file() and f.suffix == ".md"
                and f.name != "SKILL.md"):
            findings.append(
                (WARN, f.name, 0,
                 f"markdown file '{f.name}' is in skill root — "
                 f"move to references/")
            )
    return findings


@rule('references/authoring.md:24')
def rule_1_4_schemas_top_level(skill_dir: Path) -> List[Finding]:
    """JSON/YAML schemas MUST live at top-level ``schemas/``,
    not under ``references/``.

    Rule: references/authoring.md:24
    """
    findings: List[Finding] = []
    refs_dir = skill_dir / "references"
    if not refs_dir.is_dir():
        return findings
    for f in refs_dir.rglob("*"):
        if f.is_file() and f.suffix in (".yaml", ".yml", ".json"):
            findings.append(
                (ERROR, f"references/{f.relative_to(refs_dir)}", 0,
                 f"schema file '{f.name}' under references/ — "
                 f"move to top-level schemas/")
            )
    return findings


@rule('references/authoring.md:107')
def rule_5_3_no_readme(skill_dir: Path) -> List[Finding]:
    """Skills MUST NOT have a README.md.

    Rule: references/authoring.md:107
    """
    if (skill_dir / "README.md").exists():
        return [
            (ERROR, "README.md", 0,
             "skills MUST NOT have a README.md — "
             "SKILL.md is the single source of truth")
        ]
    return []


# ---------------------------------------------------------------------------
# §3 Frontmatter
# ---------------------------------------------------------------------------


@rule('references/authoring.md:69')
def rule_3_2_name_format(fields: dict) -> List[Finding]:
    """``name`` MUST be 1-64 chars, lowercase letters/digits/hyphens.

    Rule: references/authoring.md:69
    """
    findings: List[Finding] = []
    if "name" not in fields:
        findings.append(
            (ERROR, "SKILL.md", 0, "Missing 'name' field in frontmatter")
        )
        return findings
    name, lineno = fields["name"]
    if not re.match(r"^[a-z][a-z0-9-]{0,63}$", name):
        findings.append(
            (ERROR, "SKILL.md", lineno,
             f"name '{name}' invalid — must be 1-64 chars, "
             f"lowercase letters/digits/hyphens, start with letter")
        )
    return findings


@rule('references/authoring.md:70')
def rule_3_3_type_values(fields: dict) -> List[Finding]:
    """``type`` MUST be one of interface | tool | workflow | reference.

    Rule: references/authoring.md:70
    """
    findings: List[Finding] = []
    if "type" not in fields:
        findings.append(
            (ERROR, "SKILL.md", 0, "Missing 'type' field in frontmatter")
        )
        return findings
    typ, lineno = fields["type"]
    if typ not in VALID_TYPES:
        findings.append(
            (ERROR, "SKILL.md", lineno,
             f"type '{typ}' not valid — must be one of: "
             f"{', '.join(sorted(VALID_TYPES))}")
        )
    return findings


@rule('references/authoring.md:71')
def rule_3_4_description_length(fields: dict) -> List[Finding]:
    """``description`` MUST be ≤1024 chars and include trigger keywords.

    Rule: references/authoring.md:71
    """
    findings: List[Finding] = []
    if "description" not in fields:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "Missing 'description' field in frontmatter")
        )
        return findings
    desc, lineno = fields["description"]
    if len(desc) > 1024:
        findings.append(
            (ERROR, "SKILL.md", lineno,
             f"description is {len(desc)} chars (max 1024)")
        )
    if not any(p.search(desc) for p in TRIGGER_PATTERNS):
        findings.append(
            (WARN, "SKILL.md", lineno,
             "description has no trigger keywords — add 'Use when ...' "
             "or quoted trigger phrases for routing")
        )
    return findings


@rule('references/authoring.md:73')
def rule_3_5_description_person(fields: dict) -> List[Finding]:
    """``description`` MUST be in third person (no I/you/my/your).

    Rule: references/authoring.md:73
    """
    findings: List[Finding] = []
    if "description" not in fields:
        return findings
    desc, lineno = fields["description"]
    lower = desc.lower()
    bad = [
        phrase.strip() for phrase in
        ("i can ", "i help ", "you can ", "use this to ",
         "helps you ", "i will ")
        if phrase in lower
    ]
    if bad:
        findings.append(
            (WARN, "SKILL.md", lineno,
             f"description uses first/second-person phrasing "
             f"({', '.join(bad)}) — rewrite in third person")
        )
    return findings


# §3.6 (single-line frontmatter) is enforced inside parse_frontmatter
# in _helpers.py — see the YAML-folding and continuation-line checks
# at lines 79-93 of that module.


# ---------------------------------------------------------------------------
# §5 Style Guide
# ---------------------------------------------------------------------------


@rule('references/authoring.md:108')
def rule_5_4_constraints_form(
    lines: List[str], filename: str,
) -> List[Finding]:
    """Constraints MUST use RFC 2119 keywords (uppercased), and
    negative constraints MUST carry a "because [reason]" clause.

    Rule: references/authoring.md:108
    """
    findings: List[Finding] = []
    in_code = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        # Part 1: keywords must be uppercased.
        lower = line.lower()
        if "you must" in lower or "you should" in lower:
            if "you must" in line and "you MUST" not in line:
                findings.append(
                    (WARN, filename, i + 1,
                     "RFC 2119: 'must' should be uppercased to 'MUST'")
                )
            if "you should" in line and "you SHOULD" not in line:
                findings.append(
                    (WARN, filename, i + 1,
                     "RFC 2119: 'should' should be uppercased to 'SHOULD'")
                )

        # Part 2: negative constraints carry "because".
        if "MUST NOT" in line or "SHOULD NOT" in line:
            window = [line]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                if (nxt.lstrip().startswith("- ")
                        and not nxt.startswith(" ")):
                    break
                window.append(nxt)
                j += 1
            if "because" not in " ".join(window).lower():
                findings.append(
                    (WARN, filename, i + 1,
                     "negative constraint lacks 'because [reason]'")
                )
    return findings


@rule('references/authoring.md:117')
def rule_5_8_line_widths(
    lines: List[str], filename: str,
) -> List[Finding]:
    """Prose fills ≥75 chars and wraps at 80; tables ≤100 chars.

    Rule: references/authoring.md:117
    """
    findings: List[Finding] = []
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines):
        lineno = i + 1
        stripped = line.rstrip()

        if lineno == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        line_len = len(stripped)

        if stripped.startswith("|"):
            if line_len > 100:
                findings.append(
                    (WARN, filename, lineno,
                     f"table line is {line_len} chars (max 100)")
                )
            continue

        if (stripped.startswith("-") or stripped.startswith("*")
                or re.match(r'^\d+\.\s', stripped)):
            if line_len > 80:
                findings.append(
                    (ERROR, filename, lineno,
                     f"list item line is {line_len} chars (max 80)")
                )
            continue
        if (stripped.startswith("#") or stripped == ""
                or stripped.startswith("  ")
                or stripped.startswith(">")):
            continue

        if line_len > 80:
            findings.append(
                (ERROR, filename, lineno,
                 f"prose line is {line_len} chars (max 80)")
            )

        if line_len < MIN_PROSE_FILL and is_prose(stripped):
            for j in range(i + 1, len(lines)):
                nxt = lines[j].rstrip()
                if nxt == "":
                    break
                if nxt.startswith("```"):
                    break
                if is_prose(nxt):
                    first_word = nxt.split()[0] if nxt.split() else ""
                    if line_len + 1 + len(first_word) > 80:
                        break
                    findings.append(
                        (WARN, filename, lineno,
                         f"prose line is {line_len} chars "
                         f"(min fill {MIN_PROSE_FILL}) — "
                         f"reflow paragraph")
                    )
                break
    return findings


@rule('references/authoring.md:124')
def rule_5_10_emphasis_stacking(
    lines: List[str], filename: str,
) -> List[Finding]:
    """RFC 2119 keywords MUST stand alone, no CRITICAL/IMPORTANT prefix.

    Rule: references/authoring.md:124
    """
    findings: List[Finding] = []
    in_code_block = False
    pattern = re.compile(
        r'\b(CRITICAL|IMPORTANT|ALWAYS|NEVER)\b[:\s]+'
        r'.*\b(MUST|SHOULD|MAY)\b',
        re.IGNORECASE,
    )
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if pattern.search(line):
            findings.append(
                (WARN, filename, i + 1,
                 "emphasis stacking — remove CRITICAL/IMPORTANT/"
                 "ALWAYS/NEVER prefix before RFC2119 keyword")
            )
    return findings


@rule('references/authoring.md:133')
def rule_5_13_references_reachable(
    skill_dir: Path, refs_dir: Path,
) -> List[Finding]:
    """Every ``references/*.md`` MUST be reachable from SKILL.md.

    Rule: references/authoring.md:133
    """
    findings: List[Finding] = []
    all_refs = {
        p.name for p in refs_dir.iterdir() if p.suffix == ".md"
    }
    if not all_refs:
        return findings

    link_re = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
    backtick_re = re.compile(
        r'`((?:\.\.?/)?references/[^`\s]+\.md)`'
    )
    reachable: set = set()
    queue: List[Path] = [skill_dir / "SKILL.md"]
    visited: set = set()
    dangling: dict = {}

    while queue:
        cur = queue.pop(0)
        if cur in visited or not cur.exists():
            continue
        visited.add(cur)
        try:
            text = cur.read_text(encoding="utf-8")
        except OSError:
            continue
        in_refs_dir = cur.parent == refs_dir
        source_display = (
            "SKILL.md" if cur == skill_dir / "SKILL.md"
            else f"references/{cur.name}"
        )
        pairs = []
        for idx, line in enumerate(text.splitlines(), 1):
            for m in link_re.finditer(line):
                pairs.append((idx, m.group(1)))
            for m in backtick_re.finditer(line):
                pairs.append((idx, m.group(1)))
        for line_no, href in pairs:
            href = href.split("#", 1)[0].strip()
            if not href or href.startswith(
                ("http://", "https://", "mailto:")
            ):
                continue
            parts = href.split("/")
            fname = None
            if "references" in parts:
                idx = parts.index("references")
                if idx + 1 < len(parts):
                    fname = parts[idx + 1]
            elif (in_refs_dir and len(parts) == 1
                    and parts[0].endswith(".md")):
                fname = parts[0]
            if not fname:
                continue
            if fname in all_refs:
                reachable.add(fname)
                queue.append(refs_dir / fname)
            else:
                dangling.setdefault(
                    fname, (source_display, line_no)
                )

    for name in sorted(all_refs - reachable):
        findings.append(
            (WARN, f"references/{name}", 0,
             "reference file not reachable from SKILL.md "
             "via markdown links (chains allowed, but every "
             "reference MUST be reachable)")
        )
    for fname in sorted(dangling):
        src, line_no = dangling[fname]
        findings.append(
            (WARN, src, line_no,
             f"dangling reference: `references/{fname}` "
             f"is mentioned but does not exist")
        )
    return findings


@rule('references/authoring.md:134')
def rule_5_14_toc_long_files(
    ref_lines: List[str], filename: str,
) -> List[Finding]:
    """Reference files >100 lines SHOULD start with a table of contents.

    Rule: references/authoring.md:134
    """
    findings: List[Finding] = []
    if len(ref_lines) <= 100:
        return findings
    has_toc = False
    for rl in ref_lines[:30]:
        low = rl.lower()
        if ("contents" in low or "toc" in low
                or "table of contents" in low):
            has_toc = True
            break
    if not has_toc:
        findings.append(
            (WARN, filename, 0,
             "reference file >100 lines has no table of contents")
        )
    return findings


# ---------------------------------------------------------------------------
# §6 Completion Status
# ---------------------------------------------------------------------------


@rule('references/authoring.md:147')
def rule_6_1_completion_section(lines: List[str]) -> List[Finding]:
    """Every skill MUST end with a ``## Completion`` section.

    Rule: references/authoring.md:147
    """
    findings: List[Finding] = []
    for line in lines:
        if line.strip().startswith("## Completion"):
            return findings
    findings.append(
        (ERROR, "SKILL.md", 0, "Missing '## Completion' section")
    )
    return findings


@rule('references/authoring.md:148')
def rule_6_2_completion_statuses(lines: List[str]) -> List[Finding]:
    """Completion section MUST contain a table with all four
    statuses: DONE, DONE_WITH_CONCERNS, BLOCKED, NEEDS_CONTEXT.

    Rule: references/authoring.md:148
    """
    findings: List[Finding] = []
    completion_line = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Completion"):
            completion_line = i + 1
            break
    if completion_line is None:
        return findings

    # Walk forward from the heading to collect table rows until
    # the next `## ` heading or EOF.
    table_lines = []
    for i in range(completion_line, len(lines)):
        if (lines[i].strip().startswith("## ")
                and i > completion_line):
            break
        if lines[i].strip().startswith("|"):
            table_lines.append(lines[i])
    if not table_lines:
        findings.append(
            (WARN, "SKILL.md", completion_line,
             "Completion section has no status table")
        )
        return findings

    table_text = "\n".join(table_lines)
    required = ["DONE", "DONE_WITH_CONCERNS", "BLOCKED", "NEEDS_CONTEXT"]
    missing = [s for s in required if s not in table_text]
    if missing:
        findings.append(
            (WARN, "SKILL.md", completion_line,
             f"Completion table missing statuses: "
             f"{', '.join(missing)}")
        )
    return findings


# ---------------------------------------------------------------------------
# §7 Handle Policy
# ---------------------------------------------------------------------------


@rule('references/authoring.md:165')
def rule_7_1_no_other_aliases(
    lines: List[str], filename: str,
) -> List[Finding]:
    """Skill files MUST NOT contain other people's @aliases.

    Rule: references/authoring.md:165
    """
    findings: List[Finding] = []
    known_safe = {
        "@param", "@return", "@returns", "@see", "@throws",
        "@type", "@example", "@deprecated", "@override",
        "@since", "@version", "@author", "@todo", "@note",
        "@brief", "@file", "@class", "@interface",
        "@section", "@subsection", "@page", "@ref",
    }
    in_code_block = False
    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        for match in ALIAS_PATTERN.finditer(line):
            alias = match.group(0)
            if alias.lower() not in known_safe:
                findings.append(
                    (WARN, filename, i + 1,
                     f"possible alias '{alias}' — "
                     f"verify handle policy")
                )
    return findings


# ---------------------------------------------------------------------------
# §5.16 Orphan files
# ---------------------------------------------------------------------------


# Filenames that are infrastructure, not skill artefacts; never
# flagged as orphans regardless of references.
_ORPHAN_EXCLUDE = {
    "__init__.py",
    "__main__.py",
    "pyproject.toml",
    "uv.lock",
    "check.j2",         # base template extended by all checks
}


def _read_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


@rule('references/authoring.md:160')
def rule_5_16_no_orphans(skill_dir: Path) -> List[Finding]:
    """Files under ``scripts/``, ``schemas/``, ``templates/`` MUST be
    referenced by SKILL.md, scripts, prompts, or plan code; orphans
    are dead code.

    Heuristic: a candidate file is orphaned when neither its full
    name nor its base name appears anywhere in the union of all
    text under ``SKILL.md``, ``scripts/`` (excluding ``.venv``),
    ``references/``, and ``templates/`` (with the candidate's own
    text removed from the haystack to avoid self-reference).

    Rule: references/authoring.md:160
    """
    findings: List[Finding] = []

    # Build the haystack: every searchable text in the skill dir.
    haystack_parts: list[str] = []
    text_dirs = [
        skill_dir / "scripts",
        skill_dir / "references",
        skill_dir / "templates",
    ]
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        haystack_parts.append(_read_safe(skill_md))
    for d in text_dirs:
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            # Skip vendored deps and bytecode.
            if any(part in {".venv", "__pycache__"} for part in p.parts):
                continue
            if p.suffix in (".py", ".sh", ".bash", ".j2",
                            ".md", ".yaml", ".yml", ".json", ".toml"):
                haystack_parts.append(_read_safe(p))

    # Candidate orphans: schemas, check templates (non-base), skill
    # templates, scripts.
    candidates: list[tuple[str, Path]] = []

    schemas_dir = skill_dir / "schemas"
    if schemas_dir.is_dir():
        for s in schemas_dir.rglob("*.yaml"):
            candidates.append(("schemas", s))

    checks_dir = skill_dir / "templates" / "checks"
    if checks_dir.is_dir():
        for t in checks_dir.rglob("*.j2"):
            if "_meta" in t.parts:
                continue
            candidates.append(("templates/checks", t))

    skill_tmpl_dir = skill_dir / "templates" / "skill"
    if skill_tmpl_dir.is_dir():
        for t in skill_tmpl_dir.rglob("*.j2"):
            candidates.append(("templates/skill", t))

    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for s in scripts_dir.iterdir():
            if not s.is_file():
                continue
            if s.suffix not in (".py", ".sh", ".bash"):
                continue
            candidates.append(("scripts", s))

    for kind, path in candidates:
        if path.name in _ORPHAN_EXCLUDE:
            continue
        own = _read_safe(path)
        # Subtract the file's own content so self-references don't
        # mask orphan status.
        hay = "\n".join(p for p in haystack_parts if p != own)
        if path.name not in hay and path.stem not in hay:
            rel = path.relative_to(skill_dir)
            findings.append(
                (WARN, str(rel), 0,
                 f"orphan file '{path.name}' — not referenced "
                 f"by SKILL.md, scripts, or templates")
            )
    return findings

#!/usr/bin/env python3
"""
skill-lint.py — Automated convention checker for Kiro skills.

Runs the mechanical checks from the skill-reviewer Step 2 table
against a skill directory. Checks that can be fully determined by
text/pattern matching are automated here; semantic checks (trigger
uniqueness, functionality overlap, constraint quality, etc.) remain
manual and are listed in the summary as SKIPPED.

Usage:
    python3 skill-lint.py <skill-dir>
    python3 skill-lint.py ~/.kiro/skills/dev/cr-review

Exit codes:
    0  — all checks passed (may still have warnings)
    1  — one or more errors found
    2  — usage error (bad arguments, missing SKILL.md)

Output format:
    Each finding is one line:
        SEVERITY FILE:LINE: MESSAGE

    SEVERITY is one of:
        ERROR   — convention violation that MUST be fixed
        WARN    — issue that SHOULD be fixed
        SKIP    — check requires semantic judgment (manual)
        INFO    — informational note

    The final summary shows counts per severity.

Checks performed (from the Step 2 table):
    ✓ Frontmatter fields        — single lines, no YAML folding
    ✓ name field                — 1-64 chars, lowercase, hyphens only
    ✓ type field                — interface|tool|workflow|reference
    ✓ description field         — ≤ 1024 chars, has trigger keywords
    ✓ Description person        — third person, no I/you/my/your
    ✓ Type-specific structure   — required sections per skill type
    ✓ Parameters section        — required for tool and workflow skills
    ✓ Prose line width          — fills to ≥ 75 chars, wraps at 80
    ✓ List item line width      — wraps at 80
    ✓ Table formatting          — ≤ 100 chars wide
    ✓ SKILL.md length           — under 500 lines
    ✓ Reference file length     — warns over 300 lines
    ✓ Reference TOC             — files >100 lines should have TOC
    ✓ Reference reachability    — every references/*.md reachable from SKILL.md
    ✓ Dangling references       — no mentions of non-existent references/*.md
    ✓ Script location           — scripts in scripts/ subfolder
    ✓ pyproject.toml location   — per-package, not at scripts/ top level
    ✓ Completion section        — has ## Completion with status table
    ✓ Handle policy             — no @-aliases in files
    ✓ Activity tracking         — workflow steps start with activity set including target
    ✓ Step sub-step count          — max 5 sub-steps per step
    ✓ RFC2119 keywords          — constraints use MUST/SHOULD/MAY
    ✓ Negative constraint why   — "because" present after MUST NOT etc.
    ✓ Emphasis stacking         — no CRITICAL/IMPORTANT before RFC2119
    ✓ Analytics logging         — add-invocation.sh present
    ✓ Script queryability       — scripts have --help or docstring
    ✓ Bash script length        — bash scripts >10 code lines → convert to Python
    ✓ Script invocation params  — code block invocations pass all required args
    ✓ $SKILLS usage             — script invocations use $SKILLS, not ~/.kiro/skills

Checks skipped (require semantic judgment):
    ✗ Trigger phrase uniqueness
    ✗ Functionality uniqueness
    ✗ Negative trigger phrases
    ✗ Reference file focus
    ✗ Script API coverage
    ✗ Positive framing (MUST NOT vs positive alternative)
    ✗ Magic constants in scripts (uncommented values)
    ✗ Reinvention in scripts (reimplements stdlib/Linux tools)
    ✗ Pipeline handoff schemas (producer output matches consumer input)
    ✗ Env var propagation (eval-consumed scripts print shell assignments)
    ✗ Script re-narration (prose duplicating script docstrings)
    ✗ Prose script invocations (script calls outside code fences)
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# (severity, filename, line_number, message)
# line_number is 0 when the finding applies to the whole file.
Finding = Tuple[str, str, int, str]

ERROR = "ERROR"
WARN = "WARN"
SKIP = "SKIP"
INFO = "INFO"

# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

# Valid skill types per conventions.md.
VALID_TYPES = {"interface", "tool", "workflow", "reference"}

# Trigger keywords that should appear in the description so the
# router can match user intent to this skill.  We check for at
# least one of: "Use when", "MUST load when", or quoted phrases.
TRIGGER_PATTERNS = [
    re.compile(r"Use when", re.IGNORECASE),
    re.compile(r"MUST load when", re.IGNORECASE),
    re.compile(r'"[^"]+"'),  # quoted trigger phrase
]

# RFC 2119 keywords used in constraints.
RFC2119_KEYWORDS = {"MUST", "MUST NOT", "SHOULD", "SHOULD NOT", "MAY"}

# Pattern for Amazon aliases: @ followed by a login-shaped string.
# Intentionally broad — the agent filters false positives manually.
ALIAS_PATTERN = re.compile(r"@[a-z]{2,}[a-z0-9]{0,}")

# 500 chars covers shebang + imports + module docstring or usage block.
SCRIPT_HEADER_BYTES = 500


def parse_frontmatter(lines: List[str]) -> Tuple[dict, List[Finding]]:
    """Parse YAML frontmatter delimited by '---' lines.

    Returns:
        (fields_dict, findings) where fields_dict maps field names
        to (value, line_number) tuples, and findings contains any
        errors found during parsing.
    """
    findings: List[Finding] = []
    fields: dict = {}

    if not lines or lines[0].rstrip() != "---":
        findings.append(
            (ERROR, "SKILL.md", 1, "Missing opening frontmatter delimiter '---'")
        )
        return fields, findings

    # Find closing delimiter.
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close_idx = i
            break

    if close_idx is None:
        findings.append(
            (ERROR, "SKILL.md", 1, "Missing closing frontmatter delimiter '---'")
        )
        return fields, findings

    # Parse key: value pairs between delimiters.
    for i in range(1, close_idx):
        line = lines[i]
        lineno = i + 1  # 1-based

        # Check for YAML folding (multi-line values using > or |).
        if line.rstrip().endswith(">") or line.rstrip().endswith("|"):
            findings.append(
                (ERROR, "SKILL.md", lineno,
                 "Frontmatter uses YAML folding — fields must be single lines")
            )
            continue

        # Check for continuation lines (indented, no colon).
        if line.startswith(" ") and ":" not in line.split("#")[0]:
            findings.append(
                (ERROR, "SKILL.md", lineno,
                 "Frontmatter continuation line — fields must be single lines")
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
# Individual checks
# ---------------------------------------------------------------------------

def check_name_field(fields: dict) -> List[Finding]:
    """Validate the 'name' frontmatter field.

    Rules:
        - Must exist
        - 1-64 characters
        - Lowercase letters, digits, and hyphens only
        - Must start with a letter
    """
    findings = []
    if "name" not in fields:
        findings.append((ERROR, "SKILL.md", 0, "Missing 'name' field in frontmatter"))
        return findings

    name, lineno = fields["name"]
    if not re.match(r"^[a-z][a-z0-9-]{0,63}$", name):  # 1-64 chars per conventions.md
        findings.append(
            (ERROR, "SKILL.md", lineno,
             f"name '{name}' invalid — must be 1-64 chars, "
             f"lowercase letters/digits/hyphens, start with letter")
        )
    return findings


def check_type_field(fields: dict) -> List[Finding]:
    """Validate the 'type' frontmatter field.

    Must be one of: interface, tool, workflow, reference.
    """
    findings = []
    if "type" not in fields:
        findings.append((ERROR, "SKILL.md", 0, "Missing 'type' field in frontmatter"))
        return findings

    typ, lineno = fields["type"]
    if typ not in VALID_TYPES:
        findings.append(
            (ERROR, "SKILL.md", lineno,
             f"type '{typ}' not valid — must be one of: "
             f"{', '.join(sorted(VALID_TYPES))}")
        )
    return findings


def check_description_field(fields: dict) -> List[Finding]:
    """Validate the 'description' frontmatter field.

    Rules:
        - Must exist
        - ≤ 1024 characters
        - Must contain trigger keywords (Use when / MUST load when /
          quoted phrases) so the router can match user intent
    """
    findings = []
    if "description" not in fields:
        findings.append(
            (ERROR, "SKILL.md", 0, "Missing 'description' field in frontmatter")
        )
        return findings

    desc, lineno = fields["description"]
    if len(desc) > 1024:
        findings.append(
            (ERROR, "SKILL.md", lineno,
             f"description is {len(desc)} chars (max 1024)")
        )

    has_trigger = any(p.search(desc) for p in TRIGGER_PATTERNS)
    if not has_trigger:
        findings.append(
            (WARN, "SKILL.md", lineno,
             "description has no trigger keywords — add 'Use when ...' "
             "or quoted trigger phrases for routing")
        )

    return findings


def _is_prose(stripped: str) -> bool:
    """Return True if a stripped line is prose (not structural)."""
    if not stripped:
        return False
    if stripped.startswith(("#", "|", "-", "*", "`", "  ", ">")):
        return False
    if re.match(r"^\d+\.\s", stripped):
        return False
    return True


# 75 chars: conventions.md rule 8 minimum fill before wrapping.
_MIN_PROSE_FILL = 75


def check_line_widths(lines: List[str], filename: str) -> List[Finding]:
    """Check prose and table line widths.

    Rules:
        - Prose lines (outside code blocks and tables) must fill
          to ≥ 75 chars before wrapping, and wrap at 80
        - Table lines (starting with |) must be ≤ 100 chars
        - Structural lines (headers, list items, blank, indented
          code, frontmatter) are skipped for prose width checks
          but list items are still checked for the 80-char max
    """
    findings = []
    in_code_block = False
    in_frontmatter = False

    for i, line in enumerate(lines):
        lineno = i + 1
        stripped = line.rstrip()

        # Track frontmatter region.
        if lineno == 1 and stripped == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if stripped == "---":
                in_frontmatter = False
            continue

        # Track fenced code blocks.
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        line_len = len(stripped)

        # Table lines: max 100 chars.
        if stripped.startswith("|"):
            if line_len > 100:
                findings.append(
                    (WARN, filename, lineno,
                     f"table line is {line_len} chars (max 100)")
                )
            continue

        # Skip structural lines for width checks, but still
        # check list items for the 80-char max.
        if (stripped.startswith("-") or stripped.startswith("*")
                or re.match(r'^\d+\.\s', stripped)):
            if line_len > 80:
                findings.append(
                    (ERROR, filename, lineno,
                     f"list item line is {line_len} chars (max 80)")
                )
            continue
        if (stripped.startswith("#") or stripped == ""
                or stripped.startswith("  ") or stripped.startswith(">")):
            continue

        # Prose: max 80 chars.
        if line_len > 80:
            findings.append(
                (ERROR, filename, lineno,
                 f"prose line is {line_len} chars (max 80)")
            )

        # Prose: minimum fill check. A line is under-filled if
        # it is shorter than 75 chars and the next line is also
        # prose (meaning text could have continued on this line).
        if line_len < _MIN_PROSE_FILL and _is_prose(stripped):
            # Peek at the next non-blank line to see if it
            # continues the paragraph.
            for j in range(i + 1, len(lines)):
                nxt = lines[j].rstrip()
                if nxt == "":
                    break  # paragraph boundary — short is fine
                if nxt.startswith("```"):
                    break
                if _is_prose(nxt):
                    # If absorbing the first word of the next
                    # line would exceed 80 chars, the short
                    # line is acceptable — there is no room.
                    first_word = nxt.split()[0] if nxt.split() else ""
                    if line_len + 1 + len(first_word) > 80:
                        break
                    findings.append(
                        (WARN, filename, lineno,
                         f"prose line is {line_len} chars "
                         f"(min fill {_MIN_PROSE_FILL}) — "
                         f"reflow paragraph")
                    )
                break  # only check the immediate next line

    return findings


def check_file_length(lines: List[str]) -> List[Finding]:
    """SKILL.md must be under 500 lines."""
    if len(lines) > 500:
        return [
            (ERROR, "SKILL.md", 0,
             f"SKILL.md is {len(lines)} lines (max 500)")
        ]
    return []


def check_completion_section(lines: List[str]) -> List[Finding]:
    """Verify the ## Completion section exists and has a status table.

    The Completion section must contain a markdown table with at
    least the four standard statuses: DONE, DONE_WITH_CONCERNS,
    BLOCKED, NEEDS_CONTEXT.
    """
    findings = []
    completion_line = None

    for i, line in enumerate(lines):
        if line.strip().startswith("## Completion"):
            completion_line = i + 1
            break

    if completion_line is None:
        findings.append(
            (ERROR, "SKILL.md", 0, "Missing '## Completion' section")
        )
        return findings

    # Look for a table after the Completion heading.
    has_table = False
    for i in range(completion_line, len(lines)):
        if lines[i].strip().startswith("|"):
            has_table = True
            break
        # Stop if we hit another ## heading.
        if lines[i].strip().startswith("## ") and i > completion_line:
            break

    if not has_table:
        findings.append(
            (WARN, "SKILL.md", completion_line,
             "Completion section has no status table")
        )

    return findings


def check_script_location(skill_dir: Path) -> List[Finding]:
    """Scripts must live in the scripts/ subfolder, not loose in the
    skill directory.

    Checks for .py, .sh, .bash files directly in the skill dir.
    """
    findings = []
    for f in skill_dir.iterdir():
        if f.is_file() and f.suffix in (".py", ".sh", ".bash") and f.name != "SKILL.md":
            findings.append(
                (ERROR, f.name, 0,
                 f"script '{f.name}' is in skill root — move to scripts/")
            )
    return findings


def check_pyproject_location(skill_dir: Path) -> List[Finding]:
    """pyproject.toml MUST live inside each dep-using package under
    scripts/, not at scripts/ top level.

    Top-level scripts/pyproject.toml is the deprecated pattern
    where one venv covers every script. Current convention is one
    pyproject per package (see script-conventions.md § With
    dependencies).
    """
    findings = []
    scripts_dir = skill_dir / "scripts"
    top_pp = scripts_dir / "pyproject.toml"
    if top_pp.exists():
        findings.append(
            (ERROR, "scripts/pyproject.toml", 0,
             "pyproject.toml at scripts/ top level — move it into "
             "the dep-using package directory (one pyproject per "
             "package; see script-conventions.md § With dependencies)")
        )
    return findings


def check_reference_reachability(
    skill_dir: Path, refs_dir: Path
) -> List[Finding]:
    """Warn if any references/*.md is unreachable from SKILL.md via links."""
    findings: List[Finding] = []
    all_refs = {
        p.name for p in refs_dir.iterdir() if p.suffix == ".md"
    }
    if not all_refs:
        return findings

    # BFS from SKILL.md, collecting references/*.md filenames.
    # Match both markdown links [text](path) and backtick-quoted
    # `references/file.md` paths, since skills often reference
    # helper files in prose with backticks rather than links.
    link_re = re.compile(r'\[[^\]]*\]\(([^)]+)\)')
    backtick_re = re.compile(r'`((?:\.\.?/)?references/[^`\s]+\.md)`')
    reachable: set = set()
    queue: List[Path] = [skill_dir / "SKILL.md"]
    visited: set = set()
    dangling: dict = {}  # fname -> (source_display, line_no)

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
        # Collect (line_no, href) pairs from both regexes.
        pairs: List[Tuple[int, str]] = []
        for idx, line in enumerate(text.splitlines(), 1):
            for m in link_re.finditer(line):
                pairs.append((idx, m.group(1)))
            for m in backtick_re.finditer(line):
                pairs.append((idx, m.group(1)))
        for line_no, href in pairs:
            href = href.split("#", 1)[0].strip()
            if not href or href.startswith(("http://", "https://", "mailto:")):
                continue
            parts = href.split("/")
            fname = None
            if "references" in parts:
                idx = parts.index("references")
                if idx + 1 < len(parts):
                    fname = parts[idx + 1]
            elif in_refs_dir and len(parts) == 1 and parts[0].endswith(".md"):
                fname = parts[0]
            if not fname:
                continue
            if fname in all_refs:
                reachable.add(fname)
                queue.append(refs_dir / fname)
            else:
                dangling.setdefault(fname, (source_display, line_no))

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


def check_handle_policy(lines: List[str], filename: str) -> List[Finding]:
    """Skill files must not contain other people's Amazon aliases.

    We flag any @login-shaped pattern. False positives (e.g., @param
    in docstrings) are expected — the agent filters them manually.
    We skip common false positives like @param, @return, @see, etc.
    """
    findings = []
    known_safe = {"@param", "@return", "@returns", "@see", "@throws",
                  "@type", "@example", "@deprecated", "@override",
                  "@since", "@version", "@author", "@todo", "@note",
                  "@brief", "@file", "@class", "@interface",
                  "@section", "@subsection", "@page", "@ref"}
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
                     f"possible alias '{alias}' — verify handle policy")
                )
    return findings


def check_rfc2119_in_constraints(lines: List[str], filename: str) -> List[Finding]:
    """Constraint lines should use RFC 2119 keywords.

    We look for lines containing "you must", "you should", "you may"
    (case-insensitive) and verify the keyword is uppercased per
    convention. We also check that negative constraints (MUST NOT,
    SHOULD NOT) include a "because" reason.
    """
    findings = []
    in_code_block = False

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Check for lowercase RFC 2119 keywords that should be uppercase.
        # Only flag when the word appears in a constraint-like context
        # (starts with "- you" or "- You" or contains "must"/"should").
        lower = line.lower()
        if "you must" in lower or "you should" in lower:
            # Verify the keyword is actually uppercased.
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

        # Check negative constraints have "because" reason. The reason
        # may wrap onto continuation lines, so gather the full bullet
        # (this line + non-empty follow-on lines) before checking.
        if "MUST NOT" in line or "SHOULD NOT" in line:
            window = [line]
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    break
                # New top-level bullet ends the current one.
                if nxt.lstrip().startswith("- ") and not nxt.startswith(" "):
                    break
                window.append(nxt)
                j += 1
            if "because" not in " ".join(window).lower():
                findings.append(
                    (WARN, filename, i + 1,
                     "negative constraint lacks 'because [reason]'")
                )

    return findings


def check_emphasis_stacking(lines: List[str], filename: str) -> List[Finding]:
    """Flag ALL-CAPS prefixes before RFC2119 keywords.

    Patterns like "CRITICAL: You MUST", "IMPORTANT: MUST",
    or "ALWAYS MUST" cause overtriggering on Claude 4.6.
    """
    findings = []
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


def check_analytics_logging(lines: List[str]) -> List[Finding]:
    """SKILL.md must log activation via add-invocation.sh."""
    text = "\n".join(lines)
    if "add-invocation.sh" not in text:
        return [
            (ERROR, "SKILL.md", 0,
             "missing analytics logging — add "
             "add-invocation.sh call per skill-analytics")
        ]
    return []


def check_description_person(fields: dict) -> List[Finding]:
    """Description must be third person, not first or second."""
    findings = []
    if "description" not in fields:
        return findings

    desc, lineno = fields["description"]
    lower = desc.lower()
    bad = []
    for phrase in ["i can ", "i help ", "you can ", "use this to ",
                   "helps you ", "i will "]:
        if phrase in lower:
            bad.append(phrase.strip())
    if bad:
        findings.append(
            (WARN, "SKILL.md", lineno,
             f"description uses first/second person ({', '.join(bad)}) "
             f"— write in third person")
        )
    return findings


# ---------------------------------------------------------------------------
# Type-specific structure checks
# ---------------------------------------------------------------------------

def get_headings(lines: List[str]) -> List[Tuple[int, int, str]]:
    """Extract markdown headings as (line_number, level, text) tuples.

    Only extracts ATX-style headings (# prefix). Skips headings
    inside fenced code blocks.
    """
    headings = []
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


def check_interface_structure(headings: List[Tuple[int, int, str]]) -> List[Finding]:
    """Interface skills must have Invocation, API, and Commands sections."""
    findings = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}

    for required in ["invocation", "api", "commands"]:
        if required not in h2_names:
            findings.append(
                (ERROR, "SKILL.md", 0,
                 f"interface skill missing required '## {required.title()}' section")
            )
    return findings


def check_tool_structure(headings: List[Tuple[int, int, str]]) -> List[Finding]:
    """Tool skills must have a single ## Steps section and ## Parameters."""
    findings = []
    h2_names = [h[2].lower() for h in headings if h[1] == 2]

    if "steps" not in h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "tool skill missing required '## Steps' section")
        )
    if "parameters" not in h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "tool skill missing required '## Parameters' section")
        )
    return findings


def check_workflow_structure(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Workflow skills must have steps with numbered sub-steps,
    activity tracking, and a Parameters section.

    Checks:
        - ## Workflow parent section exists
        - ## Parameters section exists
        - Steps are ### subsections under ## Workflow
        - Each step starts with setting tiling activity
    """
    findings = []

    # Check for ## Parameters section.
    h2_names = {h[2].lower() for h in headings if h[1] == 2}
    if "parameters" not in h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "workflow skill missing required '## Parameters' section")
        )

    # Check for ## Workflow section.
    workflow_heading = None
    for h in headings:
        if h[1] == 2 and h[2].lower() == "workflow":
            workflow_heading = h
            break

    if workflow_heading is None:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "workflow skill missing required '## Workflow' section")
        )
        # Still check for steps even without the parent heading.
    # Find step headings (### with a number or "Step N").
    step_headings = []
    for h in headings:
        if h[1] == 3 and re.match(r"^(Step\s+)?\d+", h[2]):
            step_headings.append(h)

    if not step_headings:
        findings.append(
            (ERROR, "SKILL.md", 0,
             "workflow skill has no numbered step headings "
             "(expected ### Step N: Name or ### N. Name)")
        )
        return findings

    # Check each step has at most 5 numbered sub-steps.
    for idx, (ph_lineno, _, ph_text) in enumerate(step_headings):
        # Determine the end of this step (next step heading or EOF).
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
            # Stop at next ## heading (end of Workflow section).
            if ln.strip().startswith("## "):
                break
            if re.match(r"^\d+\.\s", ln):
                substep_count += 1
        if substep_count > 5:  # max 5 sub-steps per step (workflow-conventions.md)
            findings.append(
                (ERROR, "SKILL.md", ph_lineno,
                 f"step '{ph_text}' has {substep_count} sub-steps (max 5)")
            )

    # Check each step for activity tracking.
    # We look for "activity set" within the first ~15 lines after
    # each step heading. The label must include a target in
    # parentheses, e.g. "skill-name(<target>): Step Name".
    for ph_lineno, _, ph_text in step_headings:
        found_activity = False
        has_target = False
        # 15 lines covers heading + code block with activity set command
        search_end = min(ph_lineno + 15, len(lines))
        for j in range(ph_lineno, search_end):
            if "activity set" in lines[j]:
                found_activity = True
                if re.search(r'activity set "[^"]*\([^)]+\)', lines[j]):
                    has_target = True
                break
            # Stop if we hit the next heading.
            if j > ph_lineno and lines[j].strip().startswith("#"):
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


def check_reference_structure(
    lines: List[str],
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """Reference skills must not have procedures, API, or invocation.

    They should be passive rule sets only.
    """
    findings = []
    h2_names = {h[2].lower() for h in headings if h[1] == 2}

    forbidden = {"invocation", "api", "commands", "steps", "workflow"}
    for section in forbidden & h2_names:
        findings.append(
            (ERROR, "SKILL.md", 0,
             f"reference skill must not have '## {section.title()}' "
             f"section — references are passive rule sets")
        )
    return findings


def _parse_usage_lines(script_path: Path) -> List[Tuple[str, int, int]]:
    """Extract (command_suffix, required, optional) from Usage lines.

    Parses lines like:
        Usage: script.py <a> <b> [<c>]
        Usage: script.py create <path> <name> <cat> <type>

    Returns a list of tuples. command_suffix is "" for simple
    scripts or the subcommand name (e.g. "create") for multi-
    command scripts. required/optional are positional arg counts.
    """
    try:
        text = script_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    results = []
    # Match "Usage: scriptname args..." lines in docstrings/comments.
    for m in re.finditer(
        r'Usage:\s+\S+\s*(.*)', text
    ):
        rest = m.group(1).strip()
        if not rest:
            results.append(("", 0, 0))
            continue
        tokens = rest.split()
        # First token might be a subcommand (no angle brackets).
        subcmd = ""
        if tokens and not tokens[0].startswith(("<", "[")):
            subcmd = tokens[0]
            tokens = tokens[1:]
        req = sum(1 for t in tokens if t.startswith("<"))
        opt = sum(1 for t in tokens
                  if t.startswith("[") or t.startswith("[<"))
        results.append((subcmd, req, opt))
    return results


# Matches script invocations: python3 path/script.py or path/script.sh
_SCRIPT_INVOKE_RE = re.compile(
    r'(?:python3(?:\.\d+)?\s+)?'       # optional python3 prefix
    r'(~?/.+?/scripts/[\w.-]+\.(?:py|sh))'  # script path
)


def _join_continuation_lines(lines: List[str], start: int) -> str:
    """Join backslash-continued lines starting at index start."""
    result = lines[start].rstrip()
    i = start
    while result.endswith("\\") and i + 1 < len(lines):
        result = result[:-1] + " " + lines[i + 1].strip()
        i += 1
    return result


def check_skills_var_usage(
    lines: List[str], filename: str,
) -> List[Finding]:
    """Flag hardcoded ~/.kiro/skills/.../scripts/ paths inside fenced
    code blocks.

    Script invocations MUST use the $SKILLS variable per
    skill-builder/references/script-conventions.md § Script
    Invocation Paths. Prose mentions and Dependencies lists
    (outside code fences) keep the literal ~/.kiro/skills form
    because they are documentation paths.
    """
    findings = []
    in_code = False
    # Matches any path that includes /scripts/ — i.e., script
    # invocations. SKILL.md references (no /scripts/ segment) are
    # intentionally excluded even inside code blocks.
    pattern = re.compile(r"~/\.kiro/skills/[^\s`]*/scripts/")

    for i, line in enumerate(lines):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue
        if pattern.search(line):
            findings.append(
                (ERROR, filename, i + 1,
                 "script invocation uses hardcoded "
                 "~/.kiro/skills/...; use $SKILLS instead "
                 "(see script-conventions.md § Script "
                 "Invocation Paths)")
            )
    return findings


def check_script_invocations(
    lines: List[str], skill_dir: Path,
) -> List[Finding]:
    """Verify script invocations in code blocks pass all required
    parameters.

    Parses Usage: lines from each invoked script to determine
    required parameter count, then checks the invocation has
    enough arguments.
    """
    findings = []
    in_code = False
    # Cache: resolved script path → usage tuples
    usage_cache: dict = {}

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            continue

        # Join continuation lines for the full command.
        full_cmd = _join_continuation_lines(lines, i)

        m = _SCRIPT_INVOKE_RE.search(full_cmd)
        if not m:
            continue

        script_ref = m.group(1)
        # Resolve ~ to home.
        script_path = Path(
            script_ref.replace("~", str(Path.home()))
        )
        if not script_path.is_file():
            continue

        # Get usage info (cached).
        if script_path not in usage_cache:
            usage_cache[script_path] = _parse_usage_lines(
                script_path
            )
        usages = usage_cache[script_path]
        if not usages:
            continue

        # Extract args after the script path in the invocation.
        after_script = full_cmd[
            full_cmd.index(script_ref) + len(script_ref):
        ].strip()
        # Strip shell wrappers: trailing ), quotes.
        after_script = re.sub(r'[)"]$', '', after_script).strip()
        inv_tokens = after_script.split() if after_script else []

        # Determine which usage line matches (by subcommand).
        subcmd = ""
        arg_tokens = inv_tokens
        if inv_tokens and usages[0][0]:
            # Script uses subcommands — first token is the cmd.
            subcmd = inv_tokens[0]
            arg_tokens = inv_tokens[1:]

        matched = None
        for u_sub, u_req, u_opt in usages:
            if u_sub == subcmd:
                matched = (u_sub, u_req, u_opt)
                break
        if matched is None and usages:
            # No subcommand match — use first usage if it has
            # no subcommand.
            if not usages[0][0]:
                matched = usages[0]
        if matched is None:
            continue

        _, req, _ = matched
        # Count non-flag args (exclude shell vars like $(...)).
        actual = len([
            t for t in arg_tokens
            if not t.startswith("-")
        ])

        if actual < req:
            script_name = script_path.name
            cmd_label = (
                f"{script_name} {subcmd}" if subcmd
                else script_name
            )
            findings.append(
                (ERROR, "SKILL.md", i + 1,
                 f"invocation of {cmd_label} passes "
                 f"{actual} args (needs {req} required)")
            )

    return findings


def check_bash_script_length(skill_dir: Path) -> List[Finding]:
    """Bash scripts >10 lines MUST be converted to Python."""
    findings = []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return findings
    for script in sorted(scripts_dir.iterdir()):
        if not script.is_file() or script.suffix not in (".sh", ".bash"):
            continue
        lines = script.read_text(encoding="utf-8", errors="replace").splitlines()
        # Count non-blank, non-comment lines after shebang.
        code_lines = [
            ln for ln in lines[1:]  # skip shebang
            if ln.strip() and not ln.strip().startswith("#")
        ]
        name = f"scripts/{script.name}"
        if len(code_lines) > 10:  # 10-line threshold per convention
            findings.append(
                (WARN, name, 0,
                 f"bash script has {len(code_lines)} code lines "
                 f"(max 10) — convert to Python for better "
                 f"argument handling and maintainability")
            )
    return findings


def check_script_queryability(skill_dir: Path) -> List[Finding]:
    """Scripts in scripts/ should be self-documenting.

    A script is queryable if it has argparse, --help handling,
    or a module docstring. Without these, the LLM (and humans)
    cannot discover the tool's interface.
    """
    findings = []
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return findings

    for script in sorted(scripts_dir.iterdir()):
        if not script.is_file():
            continue
        if script.suffix not in (".py", ".sh", ".bash"):
            continue

        text = script.read_text(encoding="utf-8", errors="replace")
        name = f"scripts/{script.name}"

        if script.suffix == ".py":
            has_argparse = "argparse" in text
            has_help = "--help" in text
            has_docstring = (
                text.lstrip().startswith('"""')
                or text.lstrip().startswith("'''")
                or (text.startswith("#!") and '"""' in text[:SCRIPT_HEADER_BYTES])
            )
            if not (has_argparse or has_help or has_docstring):
                findings.append(
                    (WARN, name, 0,
                     "Python script has no argparse, --help, "
                     "or module docstring — add a queryable "
                     "interface")
                )
        elif script.suffix in (".sh", ".bash"):
            has_usage = "usage" in text.lower()[:SCRIPT_HEADER_BYTES]
            has_help = "--help" in text[:SCRIPT_HEADER_BYTES]
            has_comment = bool(
                re.search(r'^#[^!]', text, re.MULTILINE)
            )
            if not (has_usage or has_help or has_comment):
                findings.append(
                    (WARN, name, 0,
                     "Shell script has no usage info, --help, "
                     "or header comment — add a queryable "
                     "interface")
                )

    return findings


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def lint_skill(skill_dir: Path) -> List[Finding]:
    """Run all automated checks on a skill directory.

    Args:
        skill_dir: Path to the skill directory containing SKILL.md.

    Returns:
        List of findings sorted by (filename, line_number).
    """
    findings: List[Finding] = []
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        findings.append((ERROR, "SKILL.md", 0, "SKILL.md not found"))
        return findings

    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    # --- Frontmatter ---
    fields, fm_findings = parse_frontmatter(lines)
    findings.extend(fm_findings)
    findings.extend(check_name_field(fields))
    findings.extend(check_type_field(fields))
    findings.extend(check_description_field(fields))

    # --- File-level checks ---
    findings.extend(check_file_length(lines))
    findings.extend(check_line_widths(lines, "SKILL.md"))
    findings.extend(check_completion_section(lines))
    findings.extend(check_script_location(skill_dir))
    findings.extend(check_pyproject_location(skill_dir))
    findings.extend(check_script_queryability(skill_dir))
    findings.extend(check_bash_script_length(skill_dir))
    findings.extend(check_handle_policy(lines, "SKILL.md"))
    findings.extend(check_rfc2119_in_constraints(lines, "SKILL.md"))
    findings.extend(check_emphasis_stacking(lines, "SKILL.md"))
    findings.extend(check_description_person(fields))
    findings.extend(check_analytics_logging(lines))
    findings.extend(check_script_invocations(lines, skill_dir))
    findings.extend(check_skills_var_usage(lines, "SKILL.md"))

    # --- Type-specific structure ---
    headings = get_headings(lines)
    if "type" in fields:
        skill_type = fields["type"][0]
        if skill_type == "interface":
            findings.extend(check_interface_structure(headings))
        elif skill_type == "tool":
            findings.extend(check_tool_structure(headings))
        elif skill_type == "workflow":
            findings.extend(check_workflow_structure(lines, headings))
        elif skill_type == "reference":
            findings.extend(check_reference_structure(lines, headings))

    # --- Reference files ---
    refs_dir = skill_dir / "references"
    if refs_dir.is_dir():
        for ref_file in sorted(refs_dir.iterdir()):
            if ref_file.suffix == ".md":
                ref_text = ref_file.read_text(encoding="utf-8")
                ref_lines = ref_text.splitlines()
                ref_name = f"references/{ref_file.name}"
                if len(ref_lines) > 300:
                    findings.append(
                        (WARN, ref_name, 0,
                         f"reference file is {len(ref_lines)} "
                         f"lines (recommended max 300)")
                    )
                # TOC check for files over 100 lines.
                if len(ref_lines) > 100:
                    has_toc = False
                    # TOC heading typically in first 30 lines (title + intro + TOC block)
                    for rl in ref_lines[:30]:
                        low = rl.lower()
                        if ("contents" in low or "toc" in low
                                or "table of contents" in low):
                            has_toc = True
                            break
                    if not has_toc:
                        findings.append(
                            (WARN, ref_name, 0,
                             "reference file >100 lines has no "
                             "table of contents")
                        )
                # Reachability from SKILL.md is checked
                # once after this loop (see below).
                findings.extend(check_line_widths(ref_lines, ref_name))
                findings.extend(check_handle_policy(ref_lines, ref_name))
                findings.extend(
                    check_rfc2119_in_constraints(ref_lines, ref_name)
                )
                findings.extend(
                    check_emphasis_stacking(ref_lines, ref_name)
                )
                findings.extend(
                    check_skills_var_usage(ref_lines, ref_name)
                )

        # Reachability: every references/*.md file MUST
        # be reachable from SKILL.md through the markdown
        # link graph (chains allowed).
        findings.extend(
            check_reference_reachability(skill_dir, refs_dir)
        )

    # --- Skipped checks (semantic, require agent judgment) ---
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

    # Sort by filename then line number for readable output.
    findings.sort(key=lambda f: (f[1], f[2]))
    return findings


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <skill-dir>", file=sys.stderr)
        sys.exit(2)

    skill_dir = Path(sys.argv[1]).resolve()
    if not skill_dir.is_dir():
        print(f"ERROR: '{skill_dir}' is not a directory", file=sys.stderr)
        sys.exit(2)

    findings = lint_skill(skill_dir)

    # Print findings grouped by severity.
    counts = {ERROR: 0, WARN: 0, SKIP: 0, INFO: 0}
    for severity, filename, lineno, message in findings:
        counts[severity] = counts.get(severity, 0) + 1
        loc = f"{filename}:{lineno}" if lineno > 0 else filename
        print(f"  {severity:5s}  {loc:30s}  {message}")

    # Summary.
    print()
    print(
        f"Summary: {counts[ERROR]} errors, {counts[WARN]} warnings, "
        f"{counts[SKIP]} skipped (manual), {counts[INFO]} info"
    )

    sys.exit(1 if counts[ERROR] > 0 else 0)


if __name__ == "__main__":
    main()

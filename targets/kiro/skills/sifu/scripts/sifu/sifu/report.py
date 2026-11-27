"""Skill review report writer.

Ported from dojo. `accept`, `decline`, and `open-count` are the
CLI surface; `create_report`, `add_finding`, `format_report`, and
`count_findings` are the Python API used by the audit report task.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Optional

import typer

from sifu.utils import emit, fail


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECTIONS = ["Errors", "Warnings", "Info"]
SECTION_FOR_SEVERITY = {
    "Error":   "Errors",
    "Warning": "Warnings",
    "Info":    "Info",
}

HEADER = """\
# Skill Review: {name}

- **Path:** `~/.kiro/skills/{category}/{name}/`
- **Type:** {type}

## Errors

None.

## Warnings

None.

## Info

None.
"""

FINDING_RE = re.compile(r"^(\d+)\. \*\*", re.MULTILINE)
FINDING_BLOCK_RE = re.compile(
    r"^(\d+)\. (\*\*.*?)(?=\n\d+\. \*\*|\n## |\Z)",
    re.MULTILINE | re.DOTALL,
)


# ---------------------------------------------------------------------------
# Renumbering
# ---------------------------------------------------------------------------

def _renumber(text: str) -> str:
    """Renumber all findings sequentially across sections."""
    n = 0

    def _repl(_m):
        nonlocal n
        n += 1
        return f"{n}. **"

    return FINDING_RE.sub(_repl, text)


def _section_range(text: str, section: str):
    """Return (start_of_content, end_of_content) for a section."""
    heading = f"## {section}\n"
    idx = text.find(heading)
    if idx == -1:
        return None
    content_start = idx + len(heading)
    rest = text[content_start:]
    m = re.search(r"^## ", rest, re.MULTILINE)
    content_end = content_start + m.start() if m else len(text)
    return content_start, content_end


# ---------------------------------------------------------------------------
# Public Python API (called from tasks.audit_report)
# ---------------------------------------------------------------------------

def create_report(
    path: Path, name: str, category: str, typ: str,
) -> None:
    """Write the empty report skeleton."""
    path.write_text(
        HEADER.format(name=name, category=category, type=typ),
        encoding="utf-8",
    )


_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _codeify_underscore_words(text: str) -> str:
    """Wrap underscore-bearing identifiers in backticks.

    Words like ``DONE_WITH_CONCERNS`` or ``_SEARCH_PATHS`` confuse
    some markdown renderers and produce visible ``\\_`` cruft if
    backslash-escaped. Wrapping them as inline code makes them
    render verbatim everywhere. Tokens already inside a backtick
    span are left alone.
    """
    out: list[str] = []
    i = 0
    in_code = False
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "`":
            in_code = not in_code
            out.append(ch)
            i += 1
            continue
        if in_code:
            out.append(ch)
            i += 1
            continue
        m = _WORD_RE.match(text, i)
        if m:
            tok = m.group(0)
            if "_" in tok and any(c.isalnum() for c in tok):
                out.append(f"`{tok}`")
            else:
                out.append(tok)
            i = m.end()
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def add_finding(
    path: Path, severity: str, title: str, location: str,
    description: str, fix: str,
    rule_ref: str = "",
) -> int:
    """Append a finding to the section matching `severity`.

    ``rule_ref`` (when provided) is appended after the description
    as ``(`<path:rule-number>`)`` — a stable link to the rule
    source in the references markdown.

    Returns the finding's sequential number after renumbering.
    Raises ValueError if the severity is unknown or the section
    is missing.
    """
    section = SECTION_FOR_SEVERITY.get(severity)
    if section is None:
        raise ValueError(f"unknown severity: {severity}")

    text = path.read_text(encoding="utf-8")
    rng = _section_range(text, section)
    if rng is None:
        raise ValueError(f"section {section} not found in {path}")

    start, end = rng
    content = text[start:end]

    title = _codeify_underscore_words(title)
    description = _codeify_underscore_words(description)
    fix = _codeify_underscore_words(fix)

    if location:
        head = f"0. **{title}** — `{location}`\n"
    else:
        head = f"0. **{title}**\n"
    desc_line = description
    if rule_ref:
        desc_line = f"{description} (`{rule_ref}`)"
    entry = (
        head
        + f"   {desc_line}\n"
        + f"   > {fix}\n"
    )

    if re.match(r"\nNone\.\n", content):
        content = "\n" + entry + "\n"
    else:
        content = content.rstrip("\n") + "\n\n" + entry + "\n"

    text = text[:start] + content + text[end:]
    text = _renumber(text)
    path.write_text(text, encoding="utf-8")

    return len(FINDING_RE.findall(text))


def format_report(path: Path) -> None:
    """Wrap report prose at 80 chars, preserving structure."""
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n")

        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("- **")
            or stripped == "None."
        ):
            out.append(line)
            i += 1
            continue

        if FINDING_RE.match(stripped):
            out.append(line)
            i += 1
            continue

        # Blockquote ("   > ...") — collect continuation, wrap.
        if stripped.startswith("   > "):
            text = stripped[5:]
            i += 1
            while i < len(lines):
                nxt = lines[i].rstrip("\n")
                if nxt.startswith("   > "):
                    text += " " + nxt[5:]
                    i += 1
                elif nxt.startswith("     ") and nxt.strip():
                    text += " " + nxt.strip()
                    i += 1
                else:
                    break
            wrapped = textwrap.fill(
                # 75 — blockquote prefix `   > ` (5 visible cols)
                # plus 75-col body keeps the rendered line under
                # the 80-col prose ceiling enforced by authoring
                # rule 5.7.
                text, width=75,
                initial_indent="   > ",
                subsequent_indent="   > ",
            )
            out.append(wrapped + "\n")
            continue

        # Indented description ("   text") — collect, wrap.
        if stripped.startswith("   ") and not stripped.startswith("    "):
            text = stripped.strip()
            i += 1
            while i < len(lines):
                nxt = lines[i].rstrip("\n")
                if (
                    nxt.startswith("   ")
                    and not nxt.startswith("   > ")
                    and not nxt.startswith("   ~~")
                    and not FINDING_RE.match(nxt)
                    and nxt.strip()
                ):
                    text += " " + nxt.strip()
                    i += 1
                else:
                    break
            wrapped = textwrap.fill(
                # 80 — standard prose width per authoring rule
                # 5.7; description body lives at 3-space indent
                # so 80 keeps the visible line within the same
                # ceiling the rule applies to top-level prose.
                text, width=80,
                initial_indent="   ",
                subsequent_indent="   ",
            )
            out.append(wrapped + "\n")
            continue

        out.append(line)
        i += 1

    path.write_text("".join(out), encoding="utf-8")


def count_findings(path: Path) -> dict[str, int]:
    """Count findings per section in an existing report."""
    text = path.read_text(encoding="utf-8")
    counts: dict[str, int] = {"Errors": 0, "Warnings": 0, "Info": 0}
    for section in counts:
        rng = _section_range(text, section)
        if rng is None:
            continue
        body = text[rng[0]:rng[1]]
        counts[section] = len(FINDING_RE.findall(body))
    return counts


def count_open_findings(path: Path) -> int:
    """Count findings not yet closed (no ✅/⏩ marker on the first line).

    A finding is closed when it has been accepted (✅, fixed) or
    declined (⏩, dismissed). The fix loop exits when this reaches 0.
    """
    text = path.read_text(encoding="utf-8")
    open_n = 0
    for m in FINDING_BLOCK_RE.finditer(text):
        first_line = m.group(0).split("\n", 1)[0]
        if "✅" not in first_line and "⏩" not in first_line:
            open_n += 1
    return open_n


FIXED_LINE_RE = re.compile(
    r"^(\d+)\. ✅ \*\*.*?(?: \(files: ([^)]*)\))?$", re.MULTILINE)


def fixed_findings(path: Path) -> dict[int, list[str]]:
    """Map each fixed (✅) finding to the files its accept recorded."""
    text = path.read_text(encoding="utf-8")
    return {int(m.group(1)): m.group(2).split(", ") if m.group(2) else []
            for m in FIXED_LINE_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Marker (accept / decline) — used by apply phase
# ---------------------------------------------------------------------------

def _mark(path: Path, number: int, marker: str,
          reason: Optional[str], files: Optional[list[str]] = None) -> dict:
    text = path.read_text(encoding="utf-8")

    for m in FINDING_BLOCK_RE.finditer(text):
        if int(m.group(1)) != number:
            continue
        old = m.group(0)
        first_line = old.split("\n", 1)[0]
        if "✅" in first_line or "⏩" in first_line:
            return {"status": "ok", "already_marked": True}
        if marker == "decline":
            suffix = f" (declined: {reason})" if reason else ""
            new = re.sub(
                r"^(\d+\. )(.*)$",
                lambda mo: f"{mo.group(1)}⏩ {mo.group(2)}{suffix}",
                old, count=1, flags=re.MULTILINE,
            )
        else:  # accept
            suffix = f" (files: {', '.join(files)})" if files else ""
            new = re.sub(
                r"^(\d+\. )(.*)$",
                lambda mo: f"{mo.group(1)}✅ {mo.group(2)}{suffix}",
                old, count=1, flags=re.MULTILINE,
            )
        text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        return {"status": "ok", "finding": number, "marker": marker}

    raise LookupError(f"finding {number} not found in {path}")


# ---------------------------------------------------------------------------
# CLI subcommands (registered under `report` group in __main__)
# ---------------------------------------------------------------------------

def cli_accept(
    report_path: str, finding_id: int,
    file: Optional[list[str]] = typer.Option(
        None, "--file", help="Absolute path of a file the fix changed"),
) -> None:
    """`sifu.sh report accept <report.md> <id> --file <path>...` — mark
    finding fixed and record the changed files on its first line."""
    path = _resolve_report_path(report_path)
    try:
        result = _mark(path, finding_id, "accept", reason=None, files=file)
    except LookupError as e:
        fail(str(e), report_path=report_path, finding_id=finding_id)
    emit(result)


def cli_decline(
    report_path: str, finding_id: int,
    reason: str = typer.Option(
        ..., "--reason", help="Why the user rejected this finding"),
) -> None:
    """`sifu.sh report decline <report.md> <id> --reason ...`."""
    path = _resolve_report_path(report_path)
    try:
        result = _mark(path, finding_id, "decline", reason=reason)
    except LookupError as e:
        fail(str(e), report_path=report_path, finding_id=finding_id)
    emit(result)


def cli_open_count(report_path: str) -> None:
    """`sifu.sh report open-count <report.md>` — emit `{open_items}`.

    Counts findings not yet closed (no ✅/⏩). Used by the review
    fix loop's `skill-fix-apply` to decide whether another pass is
    needed.
    """
    emit({"open_items": count_open_findings(
        _resolve_report_path(report_path))})


def _resolve_report_path(report_path: str) -> Path:
    report = Path(report_path).expanduser().resolve()
    if not report.is_file():
        fail(f"report not found at {report}")
    return report

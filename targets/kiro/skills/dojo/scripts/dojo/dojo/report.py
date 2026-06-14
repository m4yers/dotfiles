"""Skill review report writer.

Ported from the original report-writer.py. The per-finding
formatting and renumbering logic is unchanged. The CLI surface
shrinks: only `accept` and `decline` are exposed via typer
because everything else is called from `pipeline.cli_assemble`
as a Python API (`create_report`, `add_finding`, `format_report`).
"""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path
from typing import Optional

import typer

from dojo.utils import emit, fail


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
# Public Python API (called from pipeline.cli_assemble)
# ---------------------------------------------------------------------------

def create_report(
    path: Path, name: str, category: str, typ: str,
) -> None:
    """Write the empty report skeleton."""
    path.write_text(
        HEADER.format(name=name, category=category, type=typ),
        encoding="utf-8",
    )


def _escape_md_underscores(text: str) -> str:
    """Escape intra-word `_` outside inline code spans.

    Markdown renders ``DONE_WITH_CONCERNS`` with a stray italic
    span on ``_WITH_``. Escaping the underscores between word
    characters preserves the literal text. Underscores inside
    backtick-delimited spans are left alone so identifiers in
    code stay verbatim.
    """
    out: list[str] = []
    in_code = False
    for i, ch in enumerate(text):
        if ch == "`":
            in_code = not in_code
            out.append(ch)
            continue
        if ch == "_" and not in_code:
            prev = text[i - 1] if i > 0 else ""
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if prev.isalnum() and nxt.isalnum():
                out.append("\\_")
                continue
        out.append(ch)
    return "".join(out)


def add_finding(
    path: Path, severity: str, title: str, location: str,
    description: str, fix: str,
    rule_ref: str = "",
) -> int:
    """Append a finding to the section matching `severity`.

    ``rule_ref`` (when provided) is appended after the description
    as ``(`<path:line>`)`` — vim ``gf``-friendly link to the rule
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

    title = _escape_md_underscores(title)
    description = _escape_md_underscores(description)
    fix = _escape_md_underscores(fix)

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


# ---------------------------------------------------------------------------
# Marker (accept / decline) — used by apply phase
# ---------------------------------------------------------------------------

def _mark(path: Path, number: int, marker: str,
          reason: Optional[str]) -> dict:
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
            new = re.sub(
                r"^(\d+\. )", r"\g<1>✅ ", old, count=1,
            )
        text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
        return {"status": "ok", "finding": number, "marker": marker}

    raise LookupError(f"finding {number} not found in {path}")


# ---------------------------------------------------------------------------
# CLI subcommands (registered under `report` group in __main__)
# ---------------------------------------------------------------------------

def cli_accept(workdir: str, finding_id: int) -> None:
    """`dojo.sh report accept <wd> <id>` — mark finding accepted."""
    path = _resolve_report_path(workdir)
    try:
        result = _mark(path, finding_id, "accept", reason=None)
    except LookupError as e:
        fail(str(e), workdir=workdir, finding_id=finding_id)
    print(json.dumps(result))


def cli_decline(
    workdir: str, finding_id: int,
    reason: str = typer.Option(
        ..., "--reason", help="Why the user rejected this finding"),
) -> None:
    """`dojo.sh report decline <wd> <id> --reason ...` — mark declined."""
    path = _resolve_report_path(workdir)
    try:
        result = _mark(path, finding_id, "decline", reason=reason)
    except LookupError as e:
        fail(str(e), workdir=workdir, finding_id=finding_id)
    print(json.dumps(result))


def cli_open_count(workdir: str) -> None:
    """`dojo.sh report open-count <wd>` — emit `{open_items}`.

    Counts findings not yet closed (no ✅/⏩). Used by the review
    fix loop's `skill-fix-apply` to report whether another pass is
    needed.
    """
    path = _resolve_report_path(workdir)
    emit({"open_items": count_open_findings(path)})


def _resolve_report_path(workdir: str) -> Path:
    """Find the report file inside a workdir's global/ scratch."""
    wd = Path(workdir).expanduser().resolve()
    report = wd / "global" / "report.md"
    if not report.is_file():
        fail(f"report not found at {report}", workdir=str(wd))
    return report

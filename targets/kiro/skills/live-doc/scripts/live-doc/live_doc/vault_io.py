"""Parse and serialise live-doc markdown.

The live doc has four H1 sections in a fixed order: a free-form intro
(before the first H1), `# Instructions`, `# Result`, `# Appendix`.
`# Instructions` and `# Appendix` MUST contain exactly these three
H2 subsections in this order:

    ## Data ingestion
    ## Data inference
    ## Data presentation

The parser raises :class:`BadDocShapeError` on any missing, duplicate,
or misordered H2 subsection; this is the structural guarantee the
refresh pipeline relies on. Heading detection is suspended inside
fenced code blocks, because script sources contain `#` comment lines
(e.g. the PEP 723 `# /// script` header).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Dict, List

H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
H3_RE = re.compile(r"^###\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^```")

STAGES = ("Data ingestion", "Data inference", "Data presentation")
STAGE_KEYS = ("ingestion", "inference", "presentation")

INSTRUCTIONS = "Instructions"
RESULT = "Result"
APPENDIX = "Appendix"


class BadDocShapeError(ValueError):
    """Raised when a live doc violates the fixed section shape."""


@dataclass
class ScriptEntry:
    """A single Appendix script: H3 description + fenced source."""

    name: str
    description: str
    source: str


@dataclass
class ResultSubsection:
    heading: str
    body: str


@dataclass
class ParsedDoc:
    intro: str
    instructions: Dict[str, str]  # stage key -> stage body
    result_header: str
    result_subsections: List[ResultSubsection]
    appendix_scripts: Dict[str, List[ScriptEntry]]  # stage key -> scripts
    run_order: Dict[str, List[str]]  # stage key -> ordered script names


# ---------------------------------------------------------------- parse

def _split_h1(text: str) -> Dict[str, List[str]]:
    """Split the doc into {section_title: [lines]}, with "" for intro."""
    sections: Dict[str, List[str]] = {"": []}
    current = ""
    in_fence = False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else H1_RE.match(line)
        if m:
            current = m.group(1)
            if current in sections:
                raise BadDocShapeError(
                    f"duplicate H1 section: {current!r}"
                )
            sections[current] = []
        else:
            sections[current].append(line)
    return sections


def _split_h2(lines: List[str]) -> Dict[str, List[str]]:
    """Split a section body into {h2_title: [lines]} preserving order."""
    out: Dict[str, List[str]] = {}
    current: str | None = None
    header_lines: List[str] = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
        m = None if in_fence else H2_RE.match(line)
        if m:
            current = m.group(1)
            if current in out:
                raise BadDocShapeError(f"duplicate H2: {current!r}")
            out[current] = []
        else:
            if current is None:
                header_lines.append(line)
            else:
                out[current].append(line)
    if header_lines:
        out["__header__"] = header_lines
    return out


def _require_three_stages(name: str, h2: Dict[str, List[str]]) -> None:
    found = [k for k in h2 if k != "__header__"]
    if found != list(STAGES):
        raise BadDocShapeError(
            f"{name!r} must contain exactly these H2 subsections in "
            f"this order: {list(STAGES)}; found {found!r}"
        )


def _parse_scripts(lines: List[str]) -> List[ScriptEntry]:
    """Parse an Appendix stage body: run-order list, then alternating
    `### <name>` + prose + fenced source blocks.
    """
    entries: List[ScriptEntry] = []
    i = 0
    # skip leading content up to first H3
    while i < len(lines) and not H3_RE.match(lines[i]):
        i += 1
    while i < len(lines):
        m = H3_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1)
        i += 1
        desc_lines: List[str] = []
        while i < len(lines) and not FENCE_RE.match(lines[i]) \
                and not H3_RE.match(lines[i]):
            desc_lines.append(lines[i])
            i += 1
        if i >= len(lines) or not FENCE_RE.match(lines[i]):
            raise BadDocShapeError(
                f"appendix script {name!r} missing fenced source"
            )
        fence_open = lines[i]
        i += 1
        src_lines: List[str] = []
        while i < len(lines) and not FENCE_RE.match(lines[i]):
            src_lines.append(lines[i])
            i += 1
        if i >= len(lines):
            raise BadDocShapeError(
                f"appendix script {name!r} fence not closed"
            )
        i += 1  # consume closing fence
        entries.append(ScriptEntry(
            name=name,
            description="\n".join(desc_lines).strip("\n"),
            source="\n".join(src_lines),
        ))
    return entries


RUN_ORDER_ITEM_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")


def _parse_run_order(lines: List[str]) -> List[str]:
    order: List[str] = []
    for line in lines:
        if H3_RE.match(line):
            break
        m = RUN_ORDER_ITEM_RE.match(line)
        if m:
            order.append(m.group(1))
    return order


def _parse_result(lines: List[str]) -> tuple[str, List[ResultSubsection]]:
    h2 = _split_h2(lines)
    header = "\n".join(h2.pop("__header__", [])).strip("\n")
    subs = [
        ResultSubsection(heading=k, body="\n".join(v).strip("\n"))
        for k, v in h2.items()
    ]
    return header, subs


def parse(text: str) -> ParsedDoc:
    sections = _split_h1(text)
    intro = "\n".join(sections.pop("", [])).strip("\n")
    for required in (INSTRUCTIONS, RESULT, APPENDIX):
        if required not in sections:
            raise BadDocShapeError(f"missing H1 section: {required!r}")

    instr_h2 = _split_h2(sections[INSTRUCTIONS])
    instr_h2.pop("__header__", None)
    _require_three_stages(INSTRUCTIONS, {**instr_h2,
                                         "__header__": []})
    instructions = {
        key: "\n".join(instr_h2[stage]).strip("\n")
        for stage, key in zip(STAGES, STAGE_KEYS)
    }

    result_header, result_subsections = _parse_result(sections[RESULT])

    app_h2 = _split_h2(sections[APPENDIX])
    app_h2.pop("__header__", None)
    _require_three_stages(APPENDIX, {**app_h2, "__header__": []})
    appendix_scripts: Dict[str, List[ScriptEntry]] = {}
    run_order: Dict[str, List[str]] = {}
    for stage, key in zip(STAGES, STAGE_KEYS):
        stage_lines = app_h2[stage]
        run_order[key] = _parse_run_order(stage_lines)
        appendix_scripts[key] = _parse_scripts(stage_lines)

    return ParsedDoc(
        intro=intro,
        instructions=instructions,
        result_header=result_header,
        result_subsections=result_subsections,
        appendix_scripts=appendix_scripts,
        run_order=run_order,
    )


# ------------------------------------------------------------- assemble

@dataclass
class AssembleParts:
    intro: str
    instructions: Dict[str, str]
    result_header: str
    result_subsections: List[ResultSubsection]
    appendix_scripts: Dict[str, List[ScriptEntry]]
    run_order: Dict[str, List[str]]


def _render_stage_appendix(order: List[str],
                           scripts: List[ScriptEntry]) -> str:
    lines: List[str] = []
    if order:
        lines.append("Run order:")
        for i, name in enumerate(order, 1):
            lines.append(f"{i}. {name}")
        lines.append("")
    for entry in scripts:
        lines.append(f"### {entry.name}")
        if entry.description:
            lines.append(entry.description)
        lines.append("```python")
        lines.append(entry.source)
        lines.append("```")
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def assemble(parts: AssembleParts) -> str:
    out: List[str] = []
    if parts.intro:
        out.append(parts.intro)
        out.append("")
    out.append(f"# {INSTRUCTIONS}")
    for stage, key in zip(STAGES, STAGE_KEYS):
        out.append(f"## {stage}")
        body = parts.instructions.get(key, "").strip("\n")
        if body:
            out.append(body)
    out.append(f"# {RESULT}")
    if parts.result_header:
        out.append(parts.result_header)
    for sub in parts.result_subsections:
        out.append(f"## {sub.heading}")
        if sub.body:
            out.append(sub.body)
    out.append(f"# {APPENDIX}")
    for stage, key in zip(STAGES, STAGE_KEYS):
        out.append(f"## {stage}")
        body = _render_stage_appendix(
            parts.run_order.get(key, []),
            parts.appendix_scripts.get(key, []),
        )
        if body:
            out.append(body)
    return "\n".join(out) + "\n"


# ----------------------------------------------------- round-trip hash

def script_hash(scripts: Dict[str, List[ScriptEntry]]) -> Dict[str, str]:
    """Return per-stage SHA-256 of concatenated (name, source) pairs."""
    out: Dict[str, str] = {}
    for key, entries in scripts.items():
        h = hashlib.sha256()
        for e in entries:
            h.update(e.name.encode())
            h.update(b"\x00")
            h.update(e.source.encode())
            h.update(b"\x00")
        out[key] = h.hexdigest()
    return out

"""Parse and serialise live-journal markdown.

A live journal is: `# <name>` (exactly one H1), zero or more topic H2
blocks each with a `Status: in-progress|done` line directly beneath
the H2, zero or more H3 sub-sections per topic (ordered by first
write), and a reserved trailing `## Appendix` H2 whose body is zero
or more `### <script-name>` entries each followed by a fenced source
block.

Topic H2s are serialised as `## T<n>: <title>` with `n` the 1-based
position in the file. The number is derived on every `assemble`, never
stored: `parse` strips a leading `T<n>: ` so :attr:`Topic.title` is
always the bare title, and :func:`find_topic` accepts either the bare
title or the `T<n>` label.

`BadJournalShapeError` is raised on duplicate H1, missing H1,
misplaced `## Appendix`, missing or out-of-range `Status:` line, or
an unclosed Appendix fence. Heading detection is suspended inside
fenced code blocks so a `# comment` in an Appendix script does not
look like an H1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(.+?)\s*$")
H3_RE = re.compile(r"^###\s+(.+?)\s*$")
FENCE_RE = re.compile(r"^```")
STATUS_RE = re.compile(r"^Status:\s*(in-progress|done)\s*$")
TOPIC_NUM_RE = re.compile(r"^T(\d+):\s+(.+?)\s*$")
TOPIC_LABEL_RE = re.compile(r"^T(\d+)$")

APPENDIX_TITLE = "Appendix"


def topic_label(index: int) -> str:
    """`T<n>` label for the 0-based topic position `index`."""
    return f"T{index + 1}"


def strip_topic_label(title: str) -> str:
    """Return the bare title, dropping a leading `T<n>: ` if present."""
    m = TOPIC_NUM_RE.match(title)
    return m.group(2) if m else title


class BadJournalShapeError(ValueError):
    """Raised when a journal violates the fixed section shape."""


@dataclass
class SubSection:
    heading: str
    body: str  # trailing newlines stripped


@dataclass
class Topic:
    title: str
    status: str
    subsections: List[SubSection] = field(default_factory=list)


@dataclass
class ScriptEntry:
    name: str
    source: str  # fenced body text, interior newlines preserved


@dataclass
class ParsedJournal:
    h1_name: str
    topics: List[Topic] = field(default_factory=list)
    appendix_scripts: List[ScriptEntry] = field(default_factory=list)


# -------------------------------------------------------------- parse

def _parse_topic(title: str, lines: List[str]) -> Topic:
    """Parse the body lines of a topic (between its H2 and the next H2)."""
    cursor = 0
    while cursor < len(lines) and lines[cursor].strip() == "":
        cursor += 1
    if cursor >= len(lines):
        raise BadJournalShapeError(
            f"topic {title!r} missing `Status:` line"
        )
    m = STATUS_RE.match(lines[cursor])
    if not m:
        raise BadJournalShapeError(
            f"topic {title!r} missing `Status: in-progress|done` "
            f"directly beneath the H2 (got {lines[cursor]!r})"
        )
    status = m.group(1)
    cursor += 1

    subs: List[SubSection] = []
    cur_heading: Optional[str] = None
    cur_body: List[str] = []
    in_fence = False
    for line in lines[cursor:]:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if cur_heading is not None:
                cur_body.append(line)
            continue
        if not in_fence:
            h3 = H3_RE.match(line)
            if h3:
                if cur_heading is not None:
                    subs.append(SubSection(
                        heading=cur_heading,
                        body="\n".join(cur_body).strip("\n"),
                    ))
                cur_heading = h3.group(1).strip()
                cur_body = []
                continue
        if cur_heading is not None:
            cur_body.append(line)
    if cur_heading is not None:
        subs.append(SubSection(
            heading=cur_heading,
            body="\n".join(cur_body).strip("\n"),
        ))
    return Topic(title=title, status=status, subsections=subs)


def _parse_appendix(lines: List[str]) -> List[ScriptEntry]:
    entries: List[ScriptEntry] = []
    i = 0
    while i < len(lines):
        m = H3_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name = m.group(1).strip()
        i += 1
        while (i < len(lines)
               and not FENCE_RE.match(lines[i])
               and not H3_RE.match(lines[i])):
            i += 1
        if i >= len(lines) or not FENCE_RE.match(lines[i]):
            raise BadJournalShapeError(
                f"appendix script {name!r} missing fenced source"
            )
        i += 1
        src_start = i
        while i < len(lines) and not FENCE_RE.match(lines[i]):
            i += 1
        if i >= len(lines):
            raise BadJournalShapeError(
                f"appendix script {name!r} fence not closed"
            )
        source = "\n".join(lines[src_start:i])
        entries.append(ScriptEntry(name=name, source=source))
        i += 1  # consume closing fence
    return entries


def parse(text: str) -> ParsedJournal:
    lines = text.splitlines()

    # Fence-aware scan for the H1 and H2 positions.
    in_fence = False
    h1: Optional[tuple[str, int]] = None
    h2_positions: List[tuple[str, int]] = []
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m1 = H1_RE.match(line)
        if m1:
            if h1 is not None:
                raise BadJournalShapeError(
                    f"duplicate H1 heading: {m1.group(1)!r}"
                )
            h1 = (m1.group(1).strip(), i)
            continue
        m2 = H2_RE.match(line)
        if m2:
            h2_positions.append((m2.group(1).strip(), i))

    if h1 is None:
        raise BadJournalShapeError("missing H1 heading")
    if not h2_positions:
        return ParsedJournal(h1_name=h1[0])

    # `## Appendix` MUST exist and be the final H2.
    appendix_idx = None
    for i, (title, _) in enumerate(h2_positions):
        if title == APPENDIX_TITLE:
            appendix_idx = i
            break
    if appendix_idx is None:
        raise BadJournalShapeError(
            "missing reserved `## Appendix` H2"
        )
    if appendix_idx != len(h2_positions) - 1:
        raise BadJournalShapeError(
            "`## Appendix` must be the final H2 heading"
        )

    topics: List[Topic] = []
    for i, (title, lineno) in enumerate(h2_positions[:-1]):
        start = lineno + 1
        end = h2_positions[i + 1][1]
        topics.append(
            _parse_topic(strip_topic_label(title), lines[start:end])
        )

    app_start = h2_positions[-1][1] + 1
    appendix_scripts = _parse_appendix(lines[app_start:])
    return ParsedJournal(
        h1_name=h1[0],
        topics=topics,
        appendix_scripts=appendix_scripts,
    )


# ----------------------------------------------------------- assemble

def assemble(parsed: ParsedJournal) -> str:
    out: List[str] = [f"# {parsed.h1_name}", ""]
    for i, topic in enumerate(parsed.topics):
        out.append(f"## {topic_label(i)}: {topic.title}")
        out.append(f"Status: {topic.status}")
        for sub in topic.subsections:
            out.append("")
            out.append(f"### {sub.heading}")
            if sub.body:
                out.append(sub.body)
        out.append("")
    out.append(f"## {APPENDIX_TITLE}")
    for entry in parsed.appendix_scripts:
        out.append("")
        out.append(f"### {entry.name}")
        out.append("```")
        out.append(entry.source)
        out.append("```")
    return "\n".join(out) + "\n"


# ----------------------------------------------------------- lookups

def find_topic(parsed: ParsedJournal, title: str) -> Optional[Topic]:
    """Look up a topic by bare title, `T<n>` label, or `T<n>: <title>`."""
    m = TOPIC_LABEL_RE.match(title)
    if m:
        index = int(m.group(1)) - 1
        if 0 <= index < len(parsed.topics):
            return parsed.topics[index]
        return None
    bare = strip_topic_label(title)
    for topic in parsed.topics:
        if topic.title == bare:
            return topic
    return None


def find_subsection(topic: Topic, heading: str) -> Optional[SubSection]:
    for sub in topic.subsections:
        if sub.heading == heading:
            return sub
    return None

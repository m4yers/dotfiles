"""Mutation entry points for `topic add`, `topic status`, `section put`,
`appendix add`. Each loads, parses, mutates the dataclass tree,
re-serialises via :func:`journal_io.assemble`, atomic-writes, and
commits the vault with a stage-specific message.
"""
from __future__ import annotations

import sys
from pathlib import Path

from live_journal.git_commit import VaultCommitError, commit
from live_journal.journal_io import (
    BadJournalShapeError,
    ParsedJournal,
    ScriptEntry,
    SubSection,
    Topic,
    assemble,
    find_subsection,
    find_topic,
    parse,
)


def _load(path: str) -> tuple[Path, ParsedJournal]:
    target = Path(path).resolve()
    if not target.is_file():
        sys.exit(f"ERROR: not a regular file: {target}")
    try:
        parsed = parse(target.read_text())
    except BadJournalShapeError as e:
        sys.exit(f"ERROR: journal shape is invalid: {e}")
    return target, parsed


def _write_and_commit(
    target: Path, parsed: ParsedJournal, message: str,
) -> None:
    text = assemble(parsed)
    if text == target.read_text():
        return  # no-op edit: nothing to write or commit
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(target)
    try:
        commit(target, message)
    except VaultCommitError as e:
        sys.exit(f"ERROR: {e}")


def topic_add(path: str, title: str) -> None:
    target, parsed = _load(path)
    if find_topic(parsed, title) is not None:
        sys.exit(f"ERROR: topic already exists: {title!r}")
    parsed.topics.append(Topic(title=title, status="in-progress"))
    _write_and_commit(
        target, parsed, f"live-journal: add topic {title}",
    )


def topic_status(path: str, title: str, status: str) -> None:
    target, parsed = _load(path)
    topic = find_topic(parsed, title)
    if topic is None:
        sys.exit(f"ERROR: topic not found: {title!r}")
    topic.status = status
    _write_and_commit(
        target, parsed, f"live-journal: mark {title} {status}",
    )


def section_put(
    path: str, topic_title: str, heading: str, body_file: str,
) -> None:
    target, parsed = _load(path)
    topic = find_topic(parsed, topic_title)
    if topic is None:
        sys.exit(f"ERROR: topic not found: {topic_title!r}")
    body_text = Path(body_file).read_text().rstrip("\n")
    existing = find_subsection(topic, heading)
    if existing is None:
        topic.subsections.append(
            SubSection(heading=heading, body=body_text)
        )
    else:
        existing.body = body_text
    _write_and_commit(
        target, parsed,
        f"live-journal: upsert {topic_title}/{heading}",
    )


def appendix_add(path: str, name: str, source_file: str) -> None:
    target, parsed = _load(path)
    source_text = Path(source_file).read_text().rstrip("\n")
    for i, entry in enumerate(parsed.appendix_scripts):
        if entry.name == name:
            parsed.appendix_scripts[i] = ScriptEntry(
                name=name, source=source_text,
            )
            break
    else:
        parsed.appendix_scripts.append(
            ScriptEntry(name=name, source=source_text)
        )
    _write_and_commit(
        target, parsed, f"live-journal: appendix add {name}",
    )

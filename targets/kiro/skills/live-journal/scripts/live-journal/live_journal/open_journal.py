"""`open` subcommand — verify, open, and emit a YAML summary.

Preflight exit code 1 covers: filename does not match
`live-journal-<name>.md`, path is not a regular file, or the vault
root is not a git repo. Opening does not commit.

Output schema (YAML written to stdout on success)::

    name:                  str      # <name> from live-journal-<name>.md
    path:                  str      # resolved absolute path to the journal
    topic_count:           int      # number of `## <title>` topic blocks
    topics:                list     # one entry per topic, in file order
                                    #   (empty list `[]` when topic_count==0):
      - title:             str      # topic H2 title
        status:            str      # `in-progress` | `done`
        subsection_count:  int      # number of `### <heading>` subsections
    last_incomplete_topic: str|null # title of the last in-progress topic,
                                    #   `null` if every topic is `done`
    appendix_script_count: int      # number of `### <script>` entries in
                                    #   the trailing `## Appendix`
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from live_journal.journal_io import BadJournalShapeError, parse

SKILLS_ROOT = Path.home() / ".kiro" / "skills"
EDITOR_SH = SKILLS_ROOT / "home" / "editor" / "scripts" / "run-editor.sh"

NAME_RE = re.compile(r"^live-journal-([a-z0-9][a-z0-9-]*)\.md$")


def _derive_name(path: Path) -> str:
    m = NAME_RE.match(path.name)
    if not m:
        sys.exit(
            f"ERROR: filename does not match `live-journal-<name>.md`: "
            f"{path.name}"
        )
    return m.group(1)


def _assert_in_git_repo(path: Path) -> None:
    result = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ERROR: vault root is not a git repo: {path.parent}")


def run(path: str) -> None:
    target = Path(path).resolve()
    if not target.is_file():
        sys.exit(f"ERROR: not a regular file: {target}")
    name = _derive_name(target)
    _assert_in_git_repo(target)

    try:
        parsed = parse(target.read_text())
    except BadJournalShapeError as e:
        sys.exit(f"ERROR: journal shape is invalid: {e}")

    editor = subprocess.run(
        [str(EDITOR_SH), "show", "file", str(target)],
        check=False,
    )
    if editor.returncode != 0:
        sys.exit(f"ERROR: editor failed to open {target}")

    last_incomplete = next(
        (t.title for t in reversed(parsed.topics)
         if t.status == "in-progress"),
        None,
    )
    lines = [
        f"name: {json.dumps(name)}",
        f"path: {json.dumps(str(target))}",
        f"topic_count: {len(parsed.topics)}",
    ]
    if not parsed.topics:
        lines.append("topics: []")
    else:
        lines.append("topics:")
        for t in parsed.topics:
            lines.append(f"  - title: {json.dumps(t.title)}")
            lines.append(f"    status: {t.status}")
            lines.append(f"    subsection_count: {len(t.subsections)}")
    lines.append(
        "last_incomplete_topic: "
        + ("null" if last_incomplete is None
           else json.dumps(last_incomplete))
    )
    lines.append(
        f"appendix_script_count: {len(parsed.appendix_scripts)}"
    )
    sys.stdout.write("\n".join(lines) + "\n")

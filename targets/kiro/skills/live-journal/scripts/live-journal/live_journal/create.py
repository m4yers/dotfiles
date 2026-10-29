"""`create` subcommand — scaffold a new live journal.

Renders the two-line scaffold (`# <name>` + `## Appendix`) via the
`template` skill, opens the file in the editor via the `editor` skill,
and makes the initial vault commit. Refuses if the file exists or if
the filename does not match `live-journal-<name>.md`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from live_journal.git_commit import VaultCommitError, commit

SKILLS_ROOT = Path.home() / ".kiro" / "skills"
TEMPLATE = (SKILLS_ROOT / "home" / "live-journal" / "templates"
            / "live-journal.md.j2")
RENDER_SH = SKILLS_ROOT / "home" / "template" / "scripts" / "render.sh"
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


def run(path: str) -> None:
    target = Path(path).resolve()
    if target.exists():
        sys.exit(f"ERROR: refusing to overwrite existing path: {target}")
    name = _derive_name(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [str(RENDER_SH), "--template", str(TEMPLATE),
         "--var", f"name={name}"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(f"ERROR: template render failed: {RENDER_SH}")
    target.write_text(result.stdout)

    editor = subprocess.run(
        [str(EDITOR_SH), "show", "file", str(target)],
        check=False,
    )
    if editor.returncode != 0:
        sys.exit(f"ERROR: editor failed to open {target}")

    try:
        commit(target, f"live-journal: create {name}")
    except VaultCommitError as e:
        sys.exit(f"ERROR: {e}")

    sys.stdout.write(f"{target}\n")

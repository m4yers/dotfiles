"""`ingest` subcommand — entry point for the refresh pipeline.

Validates the vault path, derives the doc name from the filename, then
invokes `$LOOM runtime init` with the entry seed. The resulting
workdir path is printed on stdout so the host SKILL.md captures it as
`LD_WD=$(...)`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

SKILLS_ROOT = Path.home() / ".kiro" / "skills"
LIVE_DOC_SKILL = SKILLS_ROOT / "home" / "live-doc"
LOOM_SH = SKILLS_ROOT / "home" / "loomv2" / "scripts" / "loom.sh"

NAME_RE = re.compile(r"^live-([a-z0-9][a-z0-9-]*)\.md$")


def _derive_name(path: Path) -> str:
    m = NAME_RE.match(path.name)
    if not m:
        sys.exit(
            f"ERROR: filename does not match `live-<name>.md`: "
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

    result = subprocess.run(
        [
            str(LOOM_SH), "runtime", "init",
            "--loom-root", str(LIVE_DOC_SKILL / "loom"),
            "--set", f"name={name}",
            "--set", f"vault_path={target}",
        ],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        sys.exit(result.returncode)
    sys.stdout.write(result.stdout)

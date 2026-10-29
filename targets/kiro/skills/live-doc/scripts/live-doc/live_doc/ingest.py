"""`ingest` subcommand — entry point for the refresh pipeline.

Validates the vault path, derives the doc name from the filename,
runs the cross-reference preflight, then invokes `$LOOM runtime
init` with the entry seed. The resulting workdir path is printed
on stdout so the host SKILL.md captures it as ``LD_WD=$(...)``.

Preflight exit codes:
    1  input invalid (bad filename, missing file, not in a git repo)
    2  cross-reference to another live doc detected (BLOCKED)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from live_doc.vault_io import FENCE_RE, H1_RE

SKILLS_ROOT = Path.home() / ".kiro" / "skills"
LIVE_DOC_SKILL = SKILLS_ROOT / "home" / "live-doc"
LOOM_SH = SKILLS_ROOT / "home" / "loomv2" / "scripts" / "loom.sh"

NAME_RE = re.compile(r"^live-([a-z0-9][a-z0-9-]*)\.md$")

# Token form of a live-doc filename as it may appear inside another
# doc. Matched anywhere in the raw text — including fenced Appendix
# scripts — because a script that reads another live doc still
# reaches stale referenced data on refresh.
XREF_RE = re.compile(r"live-([a-z0-9][a-z0-9-]*)\.md")

XREF_EXIT_CODE = 2


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


def _find_cross_refs(
    text: str, self_name: str,
) -> list[tuple[int, str, str]]:
    """Return ``(line_number, section, token)`` for each
    ``live-<name>.md`` token in ``text`` whose name differs from
    ``self_name``.

    ``section`` is the enclosing H1 heading text (``intro`` before
    the first H1), tracked by walking H1 lines outside fenced code
    blocks so that a ``# comment`` inside a script is not mistaken
    for a section heading. ``XREF_RE`` is applied to every line
    regardless of fence state — tokens inside fenced Appendix
    scripts still count.
    """
    hits: list[tuple[int, str, str]] = []
    section = "intro"
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            m = H1_RE.match(line)
            if m:
                section = m.group(1).strip()
        for match in XREF_RE.finditer(line):
            if match.group(1) != self_name:
                hits.append((lineno, section, match.group(0)))
    return hits


def _report_cross_refs(
    path: Path, hits: list[tuple[int, str, str]],
) -> None:
    sys.stderr.write(
        f"ERROR: refresh BLOCKED — cross-references to other live "
        f"docs found in {path}\n"
    )
    for lineno, section, token in hits:
        sys.stderr.write(
            f"  line {lineno:>4}  [{section}]  {token}\n"
        )
    sys.stderr.write(
        "Refresh the referenced docs first, or remove the "
        "references, then re-run.\n"
    )


def run(path: str) -> None:
    target = Path(path).resolve()
    if not target.is_file():
        sys.exit(f"ERROR: not a regular file: {target}")
    name = _derive_name(target)
    _assert_in_git_repo(target)

    hits = _find_cross_refs(target.read_text(), name)
    if hits:
        _report_cross_refs(target, hits)
        sys.exit(XREF_EXIT_CODE)

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

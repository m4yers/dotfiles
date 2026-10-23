"""`create` subcommand — scaffold a new live doc at a vault path and
open it in the editor. No loom, no scripts, no first refresh, no
commit; the first explicit refresh fills Result and Appendix.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SKILLS_ROOT = Path.home() / ".kiro" / "skills"
TEMPLATE = (SKILLS_ROOT / "home" / "live-doc" / "templates"
            / "live-doc.md.j2")
RENDER_SH = SKILLS_ROOT / "home" / "template" / "scripts" / "render.sh"
EDITOR_SH = SKILLS_ROOT / "home" / "editor" / "scripts" / "run-editor.sh"


def run(path: str) -> None:
    target = Path(path).resolve()
    if target.exists():
        sys.exit(f"ERROR: refusing to overwrite existing path: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [str(RENDER_SH), "--template", str(TEMPLATE)],
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

    sys.stdout.write(f"{target}\n")

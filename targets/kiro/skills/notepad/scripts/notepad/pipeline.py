"""Tool-task bodies for the notepad plan.

- `setup_layout(workdir)`  invokes `tiling layout build` and records
  a minimal output.yaml via loom's schema-bound writer.
- `editor_open(workdir, notepad_path)` invokes `editor show file
  <notepad>` and records the opened path via loom's writer.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


SKILLS_ROOT = Path.home() / ".kiro" / "skills"
TILING_SH   = SKILLS_ROOT / "home" / "tiling" / "scripts" / "run-ttm.sh"
EDITOR_SH   = SKILLS_ROOT / "home" / "editor" / "scripts" / "run-editor.sh"
LOOM_SH     = SKILLS_ROOT / "home" / "loom" / "scripts" / "loom.sh"


def _loom_output_init(workdir: Path, task_id: str) -> None:
    subprocess.run(
        [str(LOOM_SH), "output", "init",
         str(workdir), "--task", task_id],
        check=True,
    )


def _loom_output_add(workdir: Path, task_id: str,
                     pairs: list[str]) -> None:
    args = [str(LOOM_SH), "output", "add",
            str(workdir), "--task", task_id]
    for p in pairs:
        args += ["--set", p]
    subprocess.run(args, check=True)


def setup_layout(workdir: Path) -> None:
    """Build the standard 2-pane layout and record success."""
    subprocess.run([str(TILING_SH), "layout", "build"], check=True)
    _loom_output_init(workdir, "setup-layout")
    _loom_output_add(workdir, "setup-layout", ["ok=true"])


def editor_open(workdir: Path, notepad_path: Path) -> None:
    """Open notepad.md in the EDITOR pane and record the path."""
    subprocess.run(
        [str(EDITOR_SH), "show", "file", str(notepad_path)],
        check=True,
    )
    _loom_output_init(workdir, "editor-open")
    _loom_output_add(workdir, "editor-open",
                     [f"path={notepad_path}"])

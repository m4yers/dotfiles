"""Tool task: scan SKILL.md descriptions for overlapping trigger
phrases between a candidate skill and every installed skill.

Used in the create pipeline to warn the user about router
collisions before any files are written. The candidate skill
does not exist on disk yet — its name and description come
from the `gather` task output.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import typer
import yaml

from loom import tool

from dojo.utils import emit, fail

ID = "check-overlaps"

SKILLS_ROOT = Path.home() / ".kiro" / "skills"

# Path layout: <skill>/scripts/dojo/dojo/tasks/<this>.py
# parents[4] = the skill directory
_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = _SKILL_ROOT / "schemas" / "overlaps.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"


def task(workdir: Path, *, depends_on_all=()):
    """Loom tool-task factory.

    Reads gather output (path resolved by loom) and scans
    installed skills for trigger phrase overlaps.
    """
    return tool(
        ID,
        cmd=[str(SHIM), "check", "overlaps",
             "--gather-output", "${task_path:gather}"],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def _parse_description(path: Path) -> Optional[str]:
    """Extract description value from SKILL.md frontmatter."""
    try:
        text = path.read_text()
    except OSError:
        return None
    m = re.search(
        r'^description:\s*(.+?)(?:\n---|\n[a-z]+:)',
        text,
        re.MULTILINE | re.DOTALL,
    )
    if not m:
        return None
    return ' '.join(m.group(1).split())


def _extract_triggers(desc: str) -> set[str]:
    """Lower-cased quoted phrases from a description string."""
    return {t.lower() for t in re.findall(r'"([^"]+)"', desc)}


def run(name: str, description: str) -> dict:
    """Scan installed skills for trigger overlaps.

    Skips any existing skill named `name` (it might be the
    candidate being re-run, or simply an irrelevant peer).
    Returns a dict matching `schemas/overlaps.yaml`.
    """
    candidate_triggers = _extract_triggers(description)
    if not candidate_triggers:
        return {"has_overlaps": False, "overlaps": []}

    _SKIP = {".venv", "node_modules", "__pycache__",
             "site-packages", ".git"}
    overlaps = []
    for dirpath, dirnames, filenames in os.walk(
            SKILLS_ROOT, followlinks=True):
        dirnames[:] = [d for d in dirnames if d not in _SKIP]
        if "SKILL.md" not in filenames:
            continue
        skill_dir = Path(dirpath)
        if skill_dir.name == name:
            continue
        try:
            rel = skill_dir.relative_to(SKILLS_ROOT)
        except ValueError:
            continue
        if any(p in _SKIP for p in rel.parts):
            continue
        other_desc = _parse_description(skill_dir / "SKILL.md")
        if not other_desc:
            continue
        common = candidate_triggers & _extract_triggers(other_desc)
        if common:
            overlaps.append({
                "skill": str(rel),
                "reason": ", ".join(sorted(common)),
            })

    overlaps.sort(key=lambda o: o["skill"])
    return {"has_overlaps": bool(overlaps), "overlaps": overlaps}


def cli_check(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="Candidate skill name (required without --gather-output)"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d",
        help="Candidate description (required without --gather-output)"),
    gather_output: Optional[Path] = typer.Option(
        None, "--gather-output",
        help="Path to gather/output.yaml (loom-driven mode)"),
) -> None:
    """`dojo.sh check overlaps ...` — emit YAML overlaps.

    Two modes:
    - `--gather-output <path>` (loom-driven) — reads gather output.
    - `--name N --description D` (manual) — direct args.
    """
    if gather_output is not None:
        if not gather_output.exists():
            fail(f"gather output not found at {gather_output}")
        gather = yaml.safe_load(gather_output.read_text())
        name = gather.get("name")
        description = gather.get("description")
    if not (name and description):
        fail("either --gather-output or both --name and --description required")
    emit(run(name, description))

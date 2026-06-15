"""Tool task: validate that a candidate skill name is kebab-case.

Exits non-zero on validation failure so loom marks the task
``failed``. The next call to ``runtime.next()`` then raises
``RunAborted`` and the orchestrator surfaces the failure;
downstream tasks are never scheduled.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import typer
import yaml

from loom import tool

from dojo.utils import emit, fail

ID = "check-name"

_KEBAB = re.compile(r"^[a-z][a-z0-9-]*$")

_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = _SKILL_ROOT / "schemas" / "validate.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"


def task(workdir: Path, *, depends_on_all=()):
    return tool(
        ID,
        cmd=[str(SHIM), "check", "name",
             "--gather-output", "${task_path:gather-create}"],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def run(name: str) -> dict:
    """Returns `{ok: bool, error?: str}`. Does NOT exit."""
    if _KEBAB.match(name):
        return {"ok": True}
    return {
        "ok": False,
        "error": (
            f"name '{name}' must be kebab-case "
            "(lowercase letters, digits, and hyphens; starts with a letter)"
        ),
    }


def cli_check(
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Skill name (manual mode)"),
    gather_output: Optional[Path] = typer.Option(
        None, "--gather-output",
        help="Path to gather/output.yaml (loom-driven mode)"),
) -> None:
    """`dojo.sh check name ...` — exit non-zero on invalid name."""
    if gather_output is not None:
        if not gather_output.exists():
            fail(f"gather output not found at {gather_output}")
        name = yaml.safe_load(gather_output.read_text()).get("name")
    if not name:
        fail("either --gather-output or --name required")
    result = run(name)
    emit(result)
    if not result["ok"]:
        # Make the tool subprocess fail so loom cascades.
        raise typer.Exit(code=1)

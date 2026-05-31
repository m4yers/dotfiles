"""Tool task: verify the namespace exists and the skill does not.

`location` MUST point to an existing directory under
`~/.kiro/skills/`. `<location>/<name>/` MUST NOT exist (we
refuse to overwrite). Exits non-zero on either failure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from loom import tool

from dojo.utils import emit, fail

ID = "check-location"

SKILLS_ROOT = Path.home() / ".kiro" / "skills"

_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = _SKILL_ROOT / "schemas" / "validate.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"


def task(workdir: Path, *, depends_on_all=()):
    return tool(
        ID,
        cmd=[str(SHIM), "check", "location",
             "--gather-output", "${task_path:gather}"],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def run(location: str, name: str) -> dict:
    """Returns `{ok: bool, error?: str}`."""
    ns_dir = SKILLS_ROOT / location
    if not ns_dir.is_dir():
        return {
            "ok": False,
            "error": f"namespace '{location}' does not exist at {ns_dir}",
        }
    skill_dir = ns_dir / name
    if skill_dir.exists():
        return {
            "ok": False,
            "error": f"skill directory already exists at {skill_dir}",
        }
    return {"ok": True}


def cli_check(
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="Skill name"),
    location: Optional[str] = typer.Option(
        None, "--location", "-l", help="Namespace path"),
    gather_output: Optional[Path] = typer.Option(
        None, "--gather-output",
        help="Path to gather/output.yaml (loom-driven mode)"),
) -> None:
    """`dojo.sh check location ...`."""
    if gather_output is not None:
        if not gather_output.exists():
            fail(f"gather output not found at {gather_output}")
        gather = yaml.safe_load(gather_output.read_text())
        name = gather.get("name")
        location = gather.get("location")
    if not (name and location):
        fail("either --gather-output or both --name and --location required")
    result = run(location, name)
    emit(result)
    if not result["ok"]:
        raise typer.Exit(code=1)

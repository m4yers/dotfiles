"""Tool task: emit a final summary of the workflow run.

Reads the final-review (or user-review for update) decision
and the create / apply-changes file manifests, then writes a
summary against `schemas/summary.yaml`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
import yaml

from loom import tool

from dojo.utils import emit, fail

ID = "summary"

_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = _SKILL_ROOT / "schemas" / "summary.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"


def task(workdir: Path, *, depends_on_all=()):
    return tool(
        ID,
        cmd=[str(SHIM), "pipeline", "summary",
             "--workdir", str(workdir)],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def _load(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


def run(workdir: Path) -> dict:
    """Build a summary by reading prior task outputs."""
    tasks_dir = workdir / "tasks"

    # Decision is the most recent human gate. Try final-review
    # first (create), then user-review (update).
    decision = (
        _load(tasks_dir / "final-review" / "output.yaml")
        or _load(tasks_dir / "user-review" / "output.yaml")
    )
    if decision is None:
        return {
            "status": "BLOCKED",
            "files_written": [],
            "notes": "no human-gate output found",
        }

    status = "DONE" if decision.get("status") == "accept" else "BLOCKED"

    # Collect files from create / create-fix / apply-changes.
    files_written: list[str] = []
    for sub in ("create", "create-fix", "apply-changes"):
        manifest = _load(tasks_dir / sub / "output.yaml")
        if manifest:
            for f in manifest.get("files", []):
                if f.get("path") not in files_written:
                    files_written.append(f["path"])

    out: dict = {"status": status, "files_written": files_written}
    if decision.get("notes"):
        out["notes"] = decision["notes"]
    return out


def cli_summary(
    workdir: Path = typer.Option(..., "--workdir"),
) -> None:
    """`dojo.sh pipeline summary --workdir <wd>`."""
    if not workdir.is_dir():
        fail(f"workdir not found: {workdir}")
    emit(run(workdir))

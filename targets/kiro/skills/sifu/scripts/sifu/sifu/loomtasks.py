"""Loom tool-task registry: `sifu.sh task <key> <input.yaml> <output.yaml>`.

Each packaged task folder's ``tool.sh`` forwards loomv2's argv
contract here. The adapter reads the materialised ``input.yaml``,
calls the task body, and writes ``output.yaml``; loom validates it
against the folder's ``io.yaml``. Task bodies signal failure via
``utils.fail`` (non-zero exit → loom ``ToolTaskError``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import mdformat
import yaml

from sifu.autochecks.checks import lint_to_findings
from sifu.tasks import (
    audit_aggregate, audit_checks, audit_report, audit_shard_plan,
    audit_topics, check_location, check_name, check_overlaps,
    design_checks, find_skill, publish, render_design,
    render_design_update, show_report,
)
from sifu import report
from sifu.utils import SKILLS_ROOT, fail


def _check_name(inp: dict, _cwd: Path) -> dict:
    result = check_name.run(inp["name"])
    if not result["ok"]:
        fail(result["error"])
    taken = [s["path"] for s in find_skill._scan_landscape()["skills"]
             if s["name"] == inp["name"]]
    if taken:
        fail(f"skill '{inp['name']}' already installed", paths=taken)
    return {"ok": True}


def _check_location(inp: dict, _cwd: Path) -> dict:
    result = check_location.run(inp["location"], inp["name"])
    if not result["ok"]:
        fail(result["error"])
    return {"skill_dir": str(SKILLS_ROOT / inp["location"] / inp["name"])}


def _check_overlaps(inp: dict, _cwd: Path) -> dict:
    return check_overlaps.run(inp["name"], inp["description"])


def _write_md(cwd: Path, text: str) -> dict:
    out = cwd / "design.md"
    # wrap 80 — authoring §5.7 prose ceiling, so the gate shows the
    # design at the same width the skill files use.
    out.write_text(mdformat.text(text, options={"wrap": 80}),
                   encoding="utf-8")
    return {"report_path": str(out.resolve())}


def _design_render(inp: dict, cwd: Path) -> dict:
    return _write_md(cwd, render_design._render(inp["design"]))


def _design_render_update(inp: dict, cwd: Path) -> dict:
    skill = {"name": inp["name"], "category": inp["category"],
             "type": inp["type"], "skill_dir": inp["skill_dir"]}
    return _write_md(cwd, render_design_update._render(
        inp["plan"], str(cwd / "input.yaml"), skill, inp["description"]))


def _design_checks(inp: dict, _cwd: Path) -> dict:
    result = design_checks.run(inp["design"])
    if not result["ok"]:
        fail(result["error"])
    return result


def _audit_autochecks(inp: dict, _cwd: Path) -> dict:
    skill_dir = Path(inp["skill_dir"]).expanduser().resolve()
    if not skill_dir.is_dir():
        fail(f"not a directory: {skill_dir}")
    return {"findings": lint_to_findings(skill_dir)}


TASKS: dict[str, Callable[[dict, Path], dict]] = {
    "check-name": _check_name,
    "check-location": _check_location,
    "check-overlaps": _check_overlaps,
    "find-skill": lambda inp, _cwd: find_skill.run(inp["name"]),
    "design-render": _design_render,
    "design-render-update": _design_render_update,
    "design-checks": _design_checks,
    "audit-autochecks": _audit_autochecks,
    "audit-topics": lambda inp, _cwd: audit_topics.run(
        inp["skill_dir"], inp["type"]),
    "audit-checks": lambda inp, _cwd: audit_checks.run(inp["topics"]),
    "audit-shard-plan": lambda inp, _cwd: audit_shard_plan.run(
        inp["checks"], inp.get("prev")),
    "audit-aggregate": lambda inp, _cwd: audit_aggregate.run(inp),
    "audit-report": lambda inp, _cwd: audit_report.run(inp),
    "show-report": lambda inp, _cwd: show_report.run(inp),
    "skill-fix-count": lambda inp, _cwd: {
        "open_items": report.count_open_findings(Path(inp["report_path"])),
        "files": inp["files"]},
    "publish-output": lambda inp, _cwd: publish.run(inp),
}


def run(key: str, input_path: Path, output_path: Path) -> None:
    body = TASKS.get(key)
    if body is None:
        fail(f"unknown task key '{key}'", known=sorted(TASKS))
    inp = yaml.safe_load(input_path.read_text(encoding="utf-8")) or {}
    out = body(inp, Path.cwd())
    output_path.write_text(
        yaml.safe_dump(out, sort_keys=False, allow_unicode=True),
        encoding="utf-8")

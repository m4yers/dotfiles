"""Tool task: assemble autochecks + check findings into report.md.

Exit of the ``audit`` subgraph. Dedupes findings on
``(file_line, title)``, orders Errors → Warnings → Info, writes
``<workdir>/report/report.md``, and emits the path plus counts.
"""
from __future__ import annotations

from pathlib import Path

from sifu import findings as findings_mod
from sifu import report as report_mod

# Input fields that carry finding lists, in report order.
FINDING_FIELDS = (
    "autochecks", "authoring", "model_awareness", "scripts",
    "secure_llm", "interface", "tool", "workflow", "reference",
    "flow", "design", "design_update",
)

_SEVERITY_ORDER = {"Error": 0, "Warning": 1, "Info": 2}


def _relative(f: dict, skill_dir: str) -> dict:
    """Strip the skill_dir prefix from file_line so absolute and relative
    citations of one site dedupe together."""
    loc = f.get("file_line", "")
    prefix = skill_dir.rstrip("/") + "/"
    return {**f, "file_line": loc[len(prefix):]} if loc.startswith(prefix) else f


def run(inp: dict) -> dict:
    raw: list[dict] = []
    for field in FINDING_FIELDS:
        raw.extend(_relative(f, inp["skill_dir"]) for f in inp.get(field) or [])
    deduped = findings_mod.deduplicate(raw)
    deduped.sort(key=lambda f: (
        _SEVERITY_ORDER.get(f.get("severity", "Info"), 99),
        f.get("file_line", ""), f.get("title", ""),
    ))

    report_dir = Path(inp["__loom"]["workdir"]) / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"
    report_mod.create_report(
        report_path, inp["name"], inp["category"], inp["type"])
    for f in deduped:
        report_mod.add_finding(
            report_path, f["severity"], f["title"],
            f.get("file_line", ""), f["description"], f["fix"],
            rule_ref=f.get("rule_ref", ""),
        )
    report_mod.format_report(report_path)
    counts = report_mod.count_findings(report_path)
    return {
        "report_path": str(report_path),
        "skill_dir": inp["skill_dir"],
        "errors": counts["Errors"],
        "warnings": counts["Warnings"],
        "infos": counts["Info"],
    }

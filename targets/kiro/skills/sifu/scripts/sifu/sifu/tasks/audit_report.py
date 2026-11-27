"""Tool task: assemble autochecks, shard and design findings into report.md.

Exit of the ``audit`` subgraph. Re-derives each finding's severity from
its rule code, merges findings that cite one rule at one file
(``findings.merge``), drops anything below the Info band, sorts
by severity then confidence, writes ``<workdir>/report/report.md`` into
the Errors / Warnings / Info band sections, and emits the path plus
counts.
"""
from __future__ import annotations

from pathlib import Path

from sifu import findings as findings_mod
from sifu import report as report_mod
from sifu import rules

# Input fields that carry finding lists, in report order.
FINDING_FIELDS = ("autochecks", "shards", "design", "design_update")

# Design-drift codes (rule-codes.md §5) have no reference rule to look up.
DESIGN_SEVERITY = {"DSN-1-1": 95, "DSN-1-2": 90, "DSN-1-3": 75}


def _severity(check_id: str) -> int:
    """The rule's own severity; agent-written values are not trusted."""
    if check_id in DESIGN_SEVERITY:
        return DESIGN_SEVERITY[check_id]
    return rules.severity_of(check_id)


def run(inp: dict) -> dict:
    raw: list[dict] = []
    for field in FINDING_FIELDS:
        for f in inp.get(field) or []:
            raw.append({**f, "severity": _severity(f["check_id"])})
    merged = [f for f in findings_mod.merge(raw)
              if f["severity"] >= rules.INFO_MIN]
    merged.sort(key=lambda f: (
        -f["severity"], -f["confidence"], f.get("file_line", ""), f["title"],
    ))

    report_dir = Path(inp["__loom"]["workdir"]) / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "report.md"
    report_mod.create_report(
        report_path, inp["name"], inp["category"], inp["type"])
    for f in merged:
        report_mod.add_finding(
            report_path, f["severity"], f["title"], f.get("file_line", ""),
            f["description"], f["fix"], f["check_id"], f["confidence"],
            also_at=f.get("also_at") or [],
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

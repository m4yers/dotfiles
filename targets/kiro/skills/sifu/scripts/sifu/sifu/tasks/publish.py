"""Tool task: run summary (exit of graph-create/update/review).

Status guard: the decision alone never yields DONE. Open findings left
in report.md downgrade to DONE_WITH_CONCERNS, and findings marked fixed
(✅) with no file recorded in report.md mean the fixes were claimed,
not applied, so the run is BLOCKED.

Files written come from report.md: each ✅ finding records the files
its fix changed (`report accept --file`); a recorded file that does not
exist under the skill or was last modified before the report was created
means the fix was claimed, not applied, so the run is BLOCKED. Optional
`files_primary` /
`files_fixes` inputs (create/update producers) add to `files_written`
but never drive status.
"""
from __future__ import annotations

from pathlib import Path

from sifu import report as report_mod


def run(inp: dict) -> dict:
    report_path = Path(inp["report_path"])
    open_items = report_mod.count_open_findings(report_path)
    fixed = report_mod.fixed_findings(report_path)
    unrecorded = [n for n, paths in fixed.items() if not paths]
    # report/ holds only report.md, so the directory mtime is the moment
    # the report was created; a fix file older than that was not written
    # by this run.
    created = report_path.parent.stat().st_mtime
    skill_dir = Path(inp["skill_dir"]).resolve()
    unapplied = sorted({
        p for paths in fixed.values() for p in paths
        if not Path(p).is_file()
        or skill_dir not in Path(p).resolve().parents
        or Path(p).stat().st_mtime < created
    })

    files: list[str] = []
    for paths in fixed.values():
        for p in paths:
            if p not in files:
                files.append(p)
    for field in ("files_primary", "files_fixes"):
        for f in inp.get(field) or []:
            if f["path"] not in files and f["action"] != "unchanged":
                files.append(f["path"])

    notes = inp["notes"]
    if inp["decision"] != "accept":
        status = "BLOCKED"
    elif unrecorded:
        status = "BLOCKED"
        notes = (notes + " " if notes else "") + (
            f"{len(unrecorded)} finding(s) marked fixed but no file was "
            "recorded")
    elif unapplied:
        status = "BLOCKED"
        notes = (notes + " " if notes else "") + (
            "recorded fix files missing, outside the skill, or older than "
            f"the report: {', '.join(unapplied)}")
    elif inp["op"] == "review" and open_items:
        status = "DONE_WITH_CONCERNS"
        notes = (notes + " " if notes else "") + (
            f"{open_items} finding(s) still open")
    else:
        status = "DONE"
    return {
        "status": status,
        "op": inp["op"],
        "skill_dir": inp["skill_dir"],
        "report_path": inp["report_path"],
        "files_written": files,
        "notes": notes,
    }

"""Workdir status reporting."""
from __future__ import annotations

from pathlib import Path

import loom
from skill_reviewer.utils import emit, fail


def cli_status(workdir: str) -> None:
    """`$REVIEWER status <wd>` — emit current run state."""
    wd = Path(workdir).expanduser().resolve()
    try:
        runtime = loom.resume(wd)
    except FileNotFoundError as e:
        fail(str(e))

    summary = runtime.status_summary()
    report_path = wd / "global" / "report.md"
    emit({
        "workdir": str(wd),
        "done": runtime.is_done(),
        "summary": summary,
        "report_path": (
            str(report_path) if report_path.exists() else None
        ),
    })

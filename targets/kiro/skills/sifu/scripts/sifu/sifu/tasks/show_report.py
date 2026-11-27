"""Tool task: re-open report.md in the editor (review fix loop header)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sifu import report as report_mod
from sifu.utils import SKILLS_ROOT, fail

EDITOR_SH = SKILLS_ROOT / "home" / "editor" / "scripts" / "run-editor.sh"

# 30s — ceiling for an interactive editor display call; a hang past
# that means a stuck pane, not normal latency.
_EDITOR_TIMEOUT = 30


def run(inp: dict) -> dict:
    report_path = Path(inp["report_path"])
    if not report_path.is_file():
        fail(f"report missing at {report_path}")
    # Display is best-effort; every failure mode is reported so the gate
    # knows whether the user saw the report.
    if not EDITOR_SH.is_file():
        print(f"warning: editor script missing at {EDITOR_SH}; report not "
              "shown", file=sys.stderr)
    else:
        try:
            res = subprocess.run(
                [str(EDITOR_SH), "show", "file", str(report_path)],
                timeout=_EDITOR_TIMEOUT, check=False,
                capture_output=True, text=True,
            )
            if res.returncode != 0:
                print(f"warning: editor exited {res.returncode}: "
                      f"{res.stderr.strip()[-400:]}", file=sys.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"warning: editor display failed: {exc}", file=sys.stderr)
    counts = report_mod.count_findings(report_path)
    return {
        "report_path": str(report_path),
        "skill_dir": inp["skill_dir"],
        "errors": counts["Errors"],
        "warnings": counts["Warnings"],
        "infos": counts["Info"],
        "open_items": report_mod.count_open_findings(report_path),
    }

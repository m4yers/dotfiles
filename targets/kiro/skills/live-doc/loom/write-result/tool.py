"""write-result — build the `# Result` section deterministically.

Header is the `Last refresh:` timestamp line only; one subsection per
presentation run with the run's stdout verbatim. No prose summaries.
"""
from __future__ import annotations

from datetime import datetime, timezone

from io_types import WriteResultInput, WriteResultOutput


def write_result(inp: WriteResultInput) -> WriteResultOutput:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return WriteResultOutput(
        header=f"Last refresh: {ts} UTC.",
        subsections=[
            {"heading": r["result_heading"], "body": r["stdout"].rstrip("\n")}
            for r in inp.presentation_runs
        ],
    )

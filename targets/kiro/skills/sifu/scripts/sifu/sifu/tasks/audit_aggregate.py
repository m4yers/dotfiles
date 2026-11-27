"""Tool task: loop latch, port of code-review's cr-review-aggregate.

Concatenates the previous wave's findings with this wave's shard
findings; the graph latch loops back while audit-shard-plan.has_more.
"""
from __future__ import annotations

from sifu.tasks.audit_shard_plan import SLOTS


def run(inp: dict) -> dict:
    findings = list(inp.get("prev_findings") or [])
    for n in range(1, SLOTS + 1):
        findings.extend(inp.get(f"shard_{n:02d}_findings") or [])
    return {"findings": findings}

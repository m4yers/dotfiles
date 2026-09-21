"""Tool body for the `review-diffs-merge` task (loomv2 native contract).

Aggregates the review-diffs reviewer outputs (SWE + the graph
variant's domain experts) into a single verdict/findings/summary
tuple:

* `verdict` = `approved` only when all PRESENT reviewer verdicts
  equal `approved`; otherwise `revise`.
* `findings` = concatenated union of all reviewer findings (in
  swe/d1/d2/d3 order). Each `message` gets a `[<reviewer_role>]`
  breadcrumb prepended so review-fix can attribute the finding.
  No dedup — every reviewer voice is preserved.
* `summary` = per-reviewer summaries joined under `### <role>`
  markdown headers in reviewer order.
"""

from __future__ import annotations

from typing import Any

from io_types import ReviewDiffsMergeInput, ReviewDiffsMergeOutput


def _reviewer_slots(
    inp: ReviewDiffsMergeInput,
) -> list[tuple[str, list[dict[str, Any]], str, str]]:
    """Return [(verdict, findings, summary, role), ...] for the
    PRESENT reviewers in swe/d1/d2/d3 order. d2/d3 are optional — a
    graph variant with fewer domain reviewers does not wire them."""
    slots = [
        (inp.verdict_swe, inp.findings_swe, inp.summary_swe, inp.role_swe),
        (inp.verdict_d1, inp.findings_d1, inp.summary_d1, inp.role_d1),
    ]
    for v, f, s, r in [
        (getattr(inp, "verdict_d2", None), getattr(inp, "findings_d2", None),
         getattr(inp, "summary_d2", None), getattr(inp, "role_d2", None)),
        (getattr(inp, "verdict_d3", None), getattr(inp, "findings_d3", None),
         getattr(inp, "summary_d3", None), getattr(inp, "role_d3", None)),
    ]:
        if v is not None:
            slots.append((v, f or [], s or "", r or ""))
    return slots


def _tag_findings(findings: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    """Prepend a `[<role>]` breadcrumb to every finding's message."""
    label = role.strip() or "unknown reviewer"
    tagged: list[dict[str, Any]] = []
    for f in findings:
        tagged.append(
            {
                "file": f["file"],
                "severity": f["severity"],
                "message": f"[{label}] {f['message']}",
            }
        )
    return tagged


def review_diffs_merge(inp: ReviewDiffsMergeInput) -> ReviewDiffsMergeOutput:
    slots = _reviewer_slots(inp)

    verdict = (
        "approved"
        if all(v == "approved" for v, _, _, _ in slots)
        else "revise"
    )

    findings: list[dict[str, Any]] = []
    summary_blocks: list[str] = []
    for _verdict, reviewer_findings, reviewer_summary, role in slots:
        findings.extend(_tag_findings(reviewer_findings, role))
        label = role.strip() or "unknown reviewer"
        summary_blocks.append(f"### {label}\n\n{reviewer_summary.strip()}")

    return ReviewDiffsMergeOutput(
        verdict=verdict,
        findings=findings,
        summary="\n\n".join(summary_blocks),
    )

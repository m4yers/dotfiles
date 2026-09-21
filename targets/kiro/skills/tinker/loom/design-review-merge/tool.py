"""Tool body for the `design-review-merge` task (loomv2 native contract).

Deterministic aggregation of three design reviewer verdicts (SWE +
two domain experts). Rule: unanimous accept → accept; any revise →
revise, with dissenter reasons concatenated under
`[<reviewer_role>]` headers in swe/d1/d2 order.
"""

from __future__ import annotations

from io_types import DesignReviewMergeInput, DesignReviewMergeOutput


def _reviewer_slots(inp: DesignReviewMergeInput) -> list[tuple[str, str, str]]:
    """Return [(decision, revise_reason, role), ...] in swe/d1/d2 order."""
    return [
        (inp.decision_swe, inp.revise_reason_swe, inp.role_swe),
        (inp.decision_d1, inp.revise_reason_d1, inp.role_d1),
        (inp.decision_d2, inp.revise_reason_d2, inp.role_d2),
    ]


def design_review_merge(inp: DesignReviewMergeInput) -> DesignReviewMergeOutput:
    slots = _reviewer_slots(inp)

    if all(decision == "accept" for decision, _, _ in slots):
        return DesignReviewMergeOutput(decision="accept", revise_reason="")

    blocks: list[str] = []
    for decision, reason, role in slots:
        if decision == "revise":
            label = role.strip() or "unknown reviewer"
            blocks.append(f"[{label}]\n{reason.strip()}")

    return DesignReviewMergeOutput(
        decision="revise",
        revise_reason="\n\n".join(blocks),
    )

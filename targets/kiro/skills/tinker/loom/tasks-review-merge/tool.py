"""Tool body for the `tasks-review-merge` task (loomv2 native contract).

Same aggregation rule as `design-review-merge`: unanimous accept →
accept; any revise → revise, with dissenter reasons concatenated
under `[<reviewer_role>]` headers in swe/d1/d2/d3 order. Also echoes
`num_tasks` verbatim so downstream fan-out predicates gate off a
single bare ref.
"""

from __future__ import annotations

from io_types import TasksReviewMergeInput, TasksReviewMergeOutput


def _reviewer_slots(inp: TasksReviewMergeInput) -> list[tuple[str, str, str]]:
    """Return [(decision, revise_reason, role), ...] for the PRESENT
    reviewers in swe/d1/d2/d3 order. d2/d3 are optional — a graph
    variant with fewer domain reviewers simply does not wire them."""
    slots = [
        (inp.decision_swe, inp.revise_reason_swe, inp.role_swe),
        (inp.decision_d1, inp.revise_reason_d1, inp.role_d1),
    ]
    for dec, reason, role in [
        (getattr(inp, "decision_d2", None), getattr(inp, "revise_reason_d2", None),
         getattr(inp, "role_d2", None)),
        (getattr(inp, "decision_d3", None), getattr(inp, "revise_reason_d3", None),
         getattr(inp, "role_d3", None)),
    ]:
        if dec is not None:
            slots.append((dec, reason or "", role or ""))
    return slots


def tasks_review_merge(inp: TasksReviewMergeInput) -> TasksReviewMergeOutput:
    slots = _reviewer_slots(inp)

    if all(decision == "accept" for decision, _, _ in slots):
        return TasksReviewMergeOutput(
            decision="accept",
            revise_reason="",
            num_tasks=inp.num_tasks,
        )

    blocks: list[str] = []
    for decision, reason, role in slots:
        if decision == "revise":
            label = role.strip() or "unknown reviewer"
            blocks.append(f"[{label}]\n{reason.strip()}")

    return TasksReviewMergeOutput(
        decision="revise",
        revise_reason="\n\n".join(blocks),
        num_tasks=inp.num_tasks,
    )

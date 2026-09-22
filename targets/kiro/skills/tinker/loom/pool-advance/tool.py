"""Tool body for the `pool-advance` task (loomv2 native contract).

Latch task of the implementation pool loop. Deterministically
advances the cursor based on the coding round's `applied` flag,
carries retry counters and the accumulated diff bundle forward
across iterations, and emits `remaining` for the latch predicate.

Retry policy: a failed round is retried up to `retry_budget`
times; after that `on_task_fail` decides — "skip" records the
task in `failed_task_ids` and moves on (the review loop sees the
gap), "abort" raises so the graph fails and the run surfaces
BLOCKED.

The engine loads this module in-process and calls `pool_advance`;
all YAML IO and schema validation is engine-owned.
"""

from __future__ import annotations

from io_types import PoolAdvanceInput, PoolAdvanceOutput

# Cap on the prior-diffs context fed to the next coding round.
_SUMMARY_BYTES = 48 * 1024

# Cap on each round's notes contribution to the bundle.
_NOTES_BYTES = 2 * 1024


def _tail(text: str, cap: int) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= cap:
        return text
    return "…(truncated)…\n" + encoded[-cap:].decode("utf-8", errors="replace")


def pool_advance(inp: PoolAdvanceInput) -> PoolAdvanceOutput:
    prev = inp.prev or {}
    retries: dict[str, int] = dict(prev.get("retries") or {})
    failed: list[str] = list(prev.get("failed_task_ids") or [])
    diff_bundle: str = prev.get("diff_bundle") or ""
    cmds_bundle: list[str] = list(prev.get("cmds_bundle") or [])
    applied_count: int = int(prev.get("applied_count") or 0)

    task_id = inp.current_task["id"]
    title = inp.current_task["title"]
    applied = bool(inp.applied)
    retry_budget = int(inp.retry_budget)

    retrying = False
    if applied:
        applied_count += 1
    else:
        retries[task_id] = retries.get(task_id, 0) + 1
        if retries[task_id] <= retry_budget:
            retrying = True
        elif inp.on_task_fail == "abort":
            raise RuntimeError(
                f"pool-advance: task {task_id!r} failed after "
                f"{retry_budget} retries and on_task_fail=abort: "
                f"{inp.error}"
            )
        else:
            failed.append(task_id)

    # Record the round in the bundle (retried rounds included, so
    # reviewers see the failed attempts too).
    status = "applied" if applied else (
        "RETRYING" if retrying else "FAILED (skipped)"
    )
    section = [f"## {task_id}: {title} ({status})"]
    if inp.error:
        section.append(f"error: {inp.error}")
    if inp.notes:
        section.append(_tail(inp.notes, _NOTES_BYTES))
    if inp.diff:
        section.append(f"```diff\n{inp.diff}\n```")
    diff_bundle = (diff_bundle + "\n\n" if diff_bundle else "") + "\n".join(section)
    cmds_bundle.extend(inp.cmds_used or [])

    next_cursor = inp.cursor if retrying else inp.cursor + 1
    remaining = (inp.total - next_cursor) + (1 if retrying else 0)

    return PoolAdvanceOutput(
        next_cursor=next_cursor,
        remaining=remaining,
        retries=retries,
        failed_task_ids=failed,
        applied_count=applied_count,
        diff_bundle=diff_bundle,
        cmds_bundle=cmds_bundle,
        prior_diffs_summary=_tail(diff_bundle, _SUMMARY_BYTES),
    )

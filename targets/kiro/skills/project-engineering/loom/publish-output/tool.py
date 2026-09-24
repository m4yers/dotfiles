"""Exit task for project-engineering: flat outcome contract.

Flattens the pipeline's terminal outputs into the single object a
composing parent consumes without reaching into internal task ids.
"""

from io_types import PublishOutputInput, PublishOutputOutput


def publish_output(inp: PublishOutputInput) -> PublishOutputOutput:
    return PublishOutputOutput(
        applied_count=inp.applied_count,
        branch=inp.branch,
        diff_bundle=inp.diff_bundle,
        diffs_verdict=inp.diffs_verdict,
        failed_task_ids=inp.failed_task_ids,
        final_decision=inp.final_decision,
        final_note=inp.final_note,
        review_summary=inp.review_summary,
        tasks_verdict=inp.tasks_verdict,
        total_tasks=inp.total_tasks,
        verify_passed=inp.verify_passed,
    )

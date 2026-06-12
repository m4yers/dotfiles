"""CLI entry point. Wires subcommands to runtime / pipeline / tasks / report."""
from __future__ import annotations

import typer

from dojo import pipeline, report, runtime, status
from dojo.tasks import (
    check_overlaps as _check_overlaps,
    check_name as _check_name,
    check_location as _check_location,
    check_naming as _check_naming,
    find_skill as _find_skill,
    render_design as _render_design,
    summary as _summary,
)
from dojo.checks import check_prompts as _check_prompts

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


# --- top-level: loom drive ---
app.command("ingest")(runtime.cli_ingest)
app.command("next")(runtime.cli_next)
app.command("complete")(runtime.cli_complete)
# Use the audit-aware status (reports report_path when present).
app.command("status")(status.cli_status)


# --- find: discovery commands ---
find_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Discovery commands.",
)
find_app.command("skill")(_find_skill.cli_find)
app.add_typer(find_app, name="find")


# --- check: validation commands ---
check_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Validation commands.",
)
check_app.command("name")(_check_name.cli_check)
check_app.command("location")(_check_location.cli_check)
check_app.command("naming")(_check_naming.cli_check)
check_app.command("overlaps")(_check_overlaps.cli_check)
check_app.command("prompts")(_check_prompts.cli_check)
app.add_typer(check_app, name="check")


# --- pipeline: loom-internal helpers ---
pipeline_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Pipeline-internal helpers (loom-invoked).",
)
pipeline_app.command("summary")(_summary.cli_summary)
pipeline_app.command("render-design")(_render_design.cli_render)
pipeline_app.command("locate")(pipeline.cli_locate)
pipeline_app.command("synth-locate")(pipeline.cli_synth_locate)
pipeline_app.command("lint")(pipeline.cli_lint)
pipeline_app.command("assemble")(pipeline.cli_assemble)
pipeline_app.command("finalize")(pipeline.cli_finalize)
pipeline_app.command("gate-decisions")(pipeline.cli_gate_decisions)
app.add_typer(pipeline_app, name="pipeline")


# --- report: apply-phase helpers (used by review-op gate) ---
report_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False,
    help="Report apply-phase helpers (review op).",
)
report_app.command("accept")(report.cli_accept)
report_app.command("decline")(report.cli_decline)
app.add_typer(report_app, name="report")


if __name__ == "__main__":
    app()

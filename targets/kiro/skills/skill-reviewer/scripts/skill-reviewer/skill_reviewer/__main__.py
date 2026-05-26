"""CLI entry point. Wires subcommands to runtime / pipeline / report."""
from __future__ import annotations

import typer

from skill_reviewer import pipeline, report, runtime, status

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

# --- top-level: loom drive ---
app.command("ingest")(runtime.cli_ingest)
app.command("next")(runtime.cli_next)
app.command("complete")(runtime.cli_complete)
app.command("status")(status.cli_status)

# --- pipeline: loom tool tasks ---
pipeline_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False)
pipeline_app.command("locate")(pipeline.cli_locate)
pipeline_app.command("lint")(pipeline.cli_lint)
pipeline_app.command("assemble")(pipeline.cli_assemble)
pipeline_app.command("finalize")(pipeline.cli_finalize)
pipeline_app.command("gate-decisions")(pipeline.cli_gate_decisions)
app.add_typer(pipeline_app, name="pipeline")

# --- report: apply phase helpers ---
report_app = typer.Typer(
    no_args_is_help=True, pretty_exceptions_enable=False)
report_app.command("accept")(report.cli_accept)
report_app.command("decline")(report.cli_decline)
app.add_typer(report_app, name="report")


if __name__ == "__main__":
    app()

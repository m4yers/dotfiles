"""CLI entry point: `sifu.sh <command>`."""
from __future__ import annotations

from pathlib import Path

import typer

from sifu import loomtasks, report
from sifu.autochecks.checks import lint_to_findings, lint_to_text
from sifu.utils import emit

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.command("task")
def cli_task(key: str, input_path: Path, output_path: Path) -> None:
    """Loom-invoked body for a packaged tool task (see loomtasks.TASKS)."""
    loomtasks.run(key, input_path, output_path)


@app.command("autochecks")
def cli_autochecks(
    skill_dir: Path,
    fmt: str = typer.Option("yaml", "--format", help="yaml or text"),
) -> None:
    """Run the deterministic linters on a skill and print findings."""
    sd = skill_dir.expanduser().resolve()
    if fmt == "text":
        print(lint_to_text(sd), end="")
    else:
        emit({"findings": lint_to_findings(sd)})


report_app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False,
                         help="Mark findings in report.md (review fix loop).")
report_app.command("accept")(report.cli_accept)
report_app.command("decline")(report.cli_decline)
report_app.command("open-count")(report.cli_open_count)
app.add_typer(report_app, name="report")


if __name__ == "__main__":
    app()

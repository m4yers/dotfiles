#!/usr/bin/env python3
"""Curator — application CLI.

Two classes of commands, both narrow.

Run-driving (orchestrator's loop):
    ingest <url-or-path>          start a fresh run
    next <workdir>                advance internal tasks; emit next batch or done
    complete <workdir> <task-id>  mark agents/human task done
    status <workdir>              aggregate verdicts; emit DONE / DONE_WITH_CONCERNS / BLOCKED / IN_PROGRESS / NEEDS_CONTEXT

Task-implementation (invoked by tasks via cmd arrays in stages.py):
    source   fetch | convert
    vault    match | replica (build | apply)
    builders init | add

All CLI output is YAML on stdout.
"""
from __future__ import annotations

import typer

from curator import builders, runtime, source, vault


app = typer.Typer(
    help="Curator — application CLI.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

# Run-driving (orchestrator-visible).
app.command("ingest")(runtime.cli_ingest)
app.command("next")(runtime.cli_next)
app.command("complete")(runtime.cli_complete)
app.command("status")(runtime.cli_status)

# Task-implementation (invoked by tasks).
app.add_typer(source.app,   name="source")
app.add_typer(vault.app,    name="vault")
app.add_typer(builders.app, name="builders")


if __name__ == "__main__":
    app()

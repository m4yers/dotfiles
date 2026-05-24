"""Typer CLI surface for the source subpackage."""
from __future__ import annotations

from typing import Annotated

import typer

from curator.source.pipeline import emit_convert, fetch
from curator.utils import emit, fail


def cli_fetch(
    url_or_path: Annotated[str, typer.Argument(
        help="URL or local file path to fetch.")],
) -> None:
    """Acquire a source. Writes the artifact into the vault and
    emits a fetch envelope on stdout."""
    result = fetch(url_or_path)
    emit(result)
    if not result.get("ok", True):
        raise typer.Exit(code=1)


def cli_convert(
    path: Annotated[str, typer.Argument(
        help="Vault-relative or absolute path to the source file.")],
    task_workdir: Annotated[str, typer.Option(
        "--task-workdir",
        help="The convert task's subdir; receives source.md sibling.")],
) -> None:
    """Read source, extract metadata, write source.md sibling, emit
    output.yaml on stdout."""
    try:
        emit_convert(path, task_workdir)
    except FileNotFoundError as e:
        fail(f"not found: {e}")
    except ValueError as e:
        fail(str(e))


app = typer.Typer(
    help="Curator source — fetch + convert.",
    no_args_is_help=True,
)
app.command("fetch")(cli_fetch)
app.command("convert")(cli_convert)

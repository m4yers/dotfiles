"""Typer CLI surface for the source subpackage."""
from __future__ import annotations

from typing import Annotated

import typer

from vault.source.pipeline import emit_convert, fetch
from vault.utils import emit, fail


def cli_fetch(
    url_or_path: Annotated[str, typer.Argument(
        help="URL or local file path to fetch.")],
) -> None:
    """Acquire a source. Writes the artifact into the vault, persists
    the fetch envelope in the source cache for `source convert`, and
    emits that envelope on stdout (see pipeline.fetch for its keys)."""
    result = fetch(url_or_path)
    emit(result)
    if not result.get("ok", True):
        raise typer.Exit(code=1)


def cli_convert(
    path: Annotated[str, typer.Argument(
        help="Vault-relative or absolute path to the source file.")],
) -> None:
    """Read source, extract metadata, write source.md into the source
    cache, emit output.yaml on stdout. Picks up the http_headers from
    the persisted fetch envelope when the artifact was fetched through
    `source fetch`. Fails with "cannot convert <path>: <reason>" for
    unsupported formats, corrupt PDFs, and PDFs with no text."""
    try:
        emit_convert(path)
    except FileNotFoundError as e:
        fail(f"not found: {e}")
    except ValueError as e:
        fail(str(e))


app = typer.Typer(
    help="Vault source — fetch + convert.",
    no_args_is_help=True,
)
app.command("fetch")(cli_fetch)
app.command("convert")(cli_convert)

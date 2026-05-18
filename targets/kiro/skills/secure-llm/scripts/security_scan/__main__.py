"""security_scan CLI — emits a YAML scan report on stdout.

Usage:

    python -m security_scan <path>

Or via the shell wrapper:

    security-scan.sh <path>

Exit code: 0 on PASS, 1 on FAIL. Tool-task dispatchers that treat
nonzero exit as task failure (curator's engine, for example) get
a clean signal without parsing the YAML.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
import yaml

from security_scan import scan_file


app = typer.Typer(
    help="Heuristic security scan over untrusted text.",
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def cli(
    ctx: typer.Context,
    path: Annotated[str, typer.Argument(
        help="Path to the input file to scan.")] = "",
) -> None:
    """Scan a file for prompt-injection / security issues."""
    if ctx.invoked_subcommand is not None:
        return
    if not path:
        typer.echo("error: path argument required", err=True)
        raise typer.Exit(code=2)
    result = scan_file(Path(path))
    print(yaml.safe_dump(result, sort_keys=False, allow_unicode=True,
                            default_flow_style=False), end="")
    if result["verdict"] == "FAIL":
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

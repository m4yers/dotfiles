"""Shared CLI utilities — YAML I/O for stdout/stderr."""
from __future__ import annotations

import sys

import typer
import yaml


def emit(obj) -> None:
    """Print a YAML envelope to stdout. The task-runner contract."""
    print(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True,
                           default_flow_style=False), end="")


def fail(msg: str, **extra) -> None:
    """Print an error envelope to stderr and exit non-zero."""
    print(yaml.safe_dump({"error": msg, **extra}, sort_keys=False),
            file=sys.stderr, end="")
    raise typer.Exit(code=1)

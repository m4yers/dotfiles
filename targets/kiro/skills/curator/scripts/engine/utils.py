"""Shared CLI utilities — YAML I/O for stdout/stderr."""
from __future__ import annotations

import sys

import typer
import yaml


def dump_yaml(data) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                            default_flow_style=False)


def emit(obj) -> None:
    """Print YAML to stdout (no trailing extra newline)."""
    print(dump_yaml(obj), end="")


def fail(msg: str, **extra) -> None:
    """Print YAML error to stderr and raise typer.Exit(1)."""
    print(dump_yaml({"error": msg, **extra}), file=sys.stderr, end="")
    raise typer.Exit(code=1)

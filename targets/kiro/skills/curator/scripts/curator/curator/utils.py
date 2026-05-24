"""Shared CLI utilities — YAML I/O for stdout/stderr + schema loader."""
from __future__ import annotations

import sys
from pathlib import Path

import typer
import yaml




def emit(obj) -> None:
    print(yaml.safe_dump(obj, sort_keys=False, allow_unicode=True,
                            default_flow_style=False), end="")


def fail(msg: str, **extra) -> None:
    print(yaml.safe_dump({"error": msg, **extra}, sort_keys=False),
            file=sys.stderr, end="")
    raise typer.Exit(code=1)

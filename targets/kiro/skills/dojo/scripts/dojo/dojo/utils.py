"""Shared helpers — emit YAML to stdout, print error-and-exit."""
from __future__ import annotations

import sys

import yaml


def emit(payload: dict) -> None:
    """Write a YAML dict to stdout. Used by tool tasks and CLI."""
    yaml.safe_dump(payload, sys.stdout, sort_keys=False)


def fail(message: str, **fields) -> None:
    """Print a YAML error envelope to stderr and exit non-zero.

    Tool tasks invoked by loom write structured failures to
    `stderr.log`; CLI use also benefits from machine-readable errors.
    """
    payload = {"error": message, **fields}
    yaml.safe_dump(payload, sys.stderr, sort_keys=False)
    sys.exit(1)

"""Meta-validate io.yaml against schemas/io.yaml.

On failure, quotes the offending field's ``description`` from
schemas/io.yaml into the exception message so the doc is delivered
inline.
"""
from __future__ import annotations

from pathlib import Path

from loom.discovery import load_io_yaml as _load


def validate_io_yaml(folder: Path):
    """Load and meta-validate ``<folder>/io.yaml``.

    Delegates to loom.discovery.load_io_yaml which already meta-validates
    and quotes field descriptions on failure.
    """
    return _load(folder)

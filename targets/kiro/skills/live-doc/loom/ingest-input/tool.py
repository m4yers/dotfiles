"""ingest-input — entry task.

Validates the seeded ``vault_path`` points at an existing regular file
whose parent is a git repo, derives ``data_dir`` from the loom
workdir, and emits ``{name, vault_path, data_dir}``.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from io_types import IngestInputInput, IngestInputOutput


def ingest_input(inp: IngestInputInput) -> IngestInputOutput:
    assert inp.loom is not None, (
        "__loom reserved input is filled by the engine at dispatch"
    )
    vault_path = Path(inp.vault_path)
    if not vault_path.is_file():
        raise ValueError(f"vault_path is not a regular file: {vault_path}")
    result = subprocess.run(
        ["git", "-C", str(vault_path.parent), "rev-parse", "--show-toplevel"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"vault root is not a git repo: {vault_path.parent}"
        )
    workdir = Path(inp.loom.workdir)
    data_dir = workdir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return IngestInputOutput(
        name=inp.name,
        vault_path=str(vault_path),
        data_dir=str(data_dir),
    )

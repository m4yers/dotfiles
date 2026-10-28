"""Git add + commit helper for the vault repo.

Stages only the target file and returns the resulting commit SHA.
Uses ``git -C <vault-root>`` to keep the invocation independent of
the caller's cwd.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class VaultCommitError(RuntimeError):
    pass


def _git(vault_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(vault_root), *args],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise VaultCommitError(
            f"git {' '.join(args)} failed in {vault_root}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _vault_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise VaultCommitError(
            f"git rev-parse --show-toplevel failed in {path.parent}: "
            f"{result.stderr.strip()}"
        )
    return Path(result.stdout.strip())


def commit(path: Path, message: str) -> str:
    """Stage ``path`` and commit with ``message``. Returns commit SHA."""
    root = _vault_root(path)
    rel = path.resolve().relative_to(root.resolve())
    _git(root, "add", "--", str(rel))
    _git(root, "commit", "-m", message, "--", str(rel))
    sha = _git(root, "rev-parse", "HEAD").strip()
    return sha

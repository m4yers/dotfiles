"""commit-vault — stage the vault file and commit with the live-doc
refresh message. Delegates to :func:`live_doc.git_commit.commit`.
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

from io_types import CommitVaultInput, CommitVaultOutput

_HERE = Path(__file__).resolve()
_PKG = _HERE.parent.parent.parent / "scripts" / "live-doc"
sys.path.insert(0, str(_PKG))

from live_doc import git_commit  # noqa: E402


def commit_vault(inp: CommitVaultInput) -> CommitVaultOutput:
    ts = _dt.datetime.now(_dt.timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )
    message = f"live-doc: refresh {inp.name} @ {ts}"
    sha = git_commit.commit(Path(inp.vault_path), message)
    return CommitVaultOutput(commit_sha=sha, message=message)

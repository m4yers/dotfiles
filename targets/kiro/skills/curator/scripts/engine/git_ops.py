"""Git operations on the vault.

Commits scoped to curator-owned paths with a structured message.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from engine import vault

CURATOR_OWNED_GLOBS = (
    "10 SOURCES/Papers",
    "10 SOURCES/Books",
    "10 SOURCES/Articles",
    "10 SOURCES/Videos",
    "12 KEYWORDS",
    "13 PEOPLE",
    "14 MODELS",
    "21 SYNTHESIS",
)


def commit(message: str) -> dict:
    """Stage curator-owned paths, commit with structured message.

    Returns {ok, commit, files} or {ok: false, reason} if nothing to commit.
    """
    _ensure_git_repo()

    # Only stage changes under curator-owned roots.
    subprocess.run(
        ["git", "-C", str(vault.VAULT_ROOT), "add", "--", *CURATOR_OWNED_GLOBS],
        check=True,
    )

    status = subprocess.run(
        ["git", "-C", str(vault.VAULT_ROOT), "diff", "--cached", "--name-status"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    if not status:
        return {"ok": False, "reason": "no changes in curator-owned paths"}

    files = [line.split("\t", 1) for line in status.splitlines()]
    # Build structured message body.
    added = [f for st, f in files if st.startswith("A")]
    modified = [f for st, f in files if st.startswith("M")]
    deleted = [f for st, f in files if st.startswith("D")]

    body_lines = [message, ""]
    if added:
        body_lines.append("added:")
        body_lines.extend(f"  {f}" for f in added)
    if modified:
        body_lines.append("updated:")
        body_lines.extend(f"  {f}" for f in modified)
    if deleted:
        body_lines.append("removed:")
        body_lines.extend(f"  {f}" for f in deleted)
    full_msg = "\n".join(body_lines)

    subprocess.run(
        ["git", "-C", str(vault.VAULT_ROOT), "commit", "-m", full_msg],
        check=True,
    )

    sha = subprocess.run(
        ["git", "-C", str(vault.VAULT_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return {
        "ok": True,
        "commit": sha,
        "added": added,
        "updated": modified,
        "removed": deleted,
    }


def recent(n: int = 20) -> dict:
    """Recent commits affecting curator-owned paths."""
    _ensure_git_repo()
    fmt = "%h%x09%aI%x09%s"
    r = subprocess.run(
        [
            "git", "-C", str(vault.VAULT_ROOT),
            "log", f"-n{n}", f"--format={fmt}",
            "--", *CURATOR_OWNED_GLOBS,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    entries = []
    for line in r.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            sha, iso, subject = parts
            entries.append({"commit": sha, "date": iso, "subject": subject})
    return {"recent": entries}


def _ensure_git_repo():
    r = subprocess.run(
        ["git", "-C", str(vault.VAULT_ROOT), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise ValueError(
            f"vault is not a git repo. Run `git init` in {vault.VAULT_ROOT} first."
        )

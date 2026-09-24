"""Tool body for the `workspace-guard` task (loomv2 native contract).

Pre-implementation git hygiene check: reports whether the workspace
tree is dirty (so the branch-gate can ask the user what to do) and
proposes a feature branch name from the ingest feature_slug.

The engine loads this module in-process and calls `workspace_guard`;
all YAML IO and schema validation is engine-owned.
"""

from __future__ import annotations

import subprocess

from io_types import WorkspaceGuardInput, WorkspaceGuardOutput

# 4 KiB — matches io.yaml `status_tail` documented cap.
_TAIL_BYTES = 4 * 1024

# Branch names stay short enough for refs and log lines.
_MAX_BRANCH_LEN = 60


def _git(workspace: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", workspace, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _tail(text: str) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= _TAIL_BYTES:
        return text
    return encoded[-_TAIL_BYTES:].decode("utf-8", errors="replace")


def workspace_guard(inp: WorkspaceGuardInput) -> WorkspaceGuardOutput:
    status = _git(inp.workspace_abs, "status", "--porcelain")
    if status.returncode != 0:
        # Non-git workspace: nothing to guard, nothing to branch.
        return WorkspaceGuardOutput(
            dirty=False,
            status_tail="",
            current_branch="",
            proposed_branch="",
        )

    porcelain = status.stdout.strip()

    branch = _git(inp.workspace_abs, "rev-parse", "--abbrev-ref", "HEAD")
    current_branch = branch.stdout.strip() if branch.returncode == 0 else ""
    if current_branch == "HEAD":
        current_branch = "DETACHED"

    slug = (inp.feature_slug or "feature").strip("-") or "feature"
    proposed = f"feature/{slug}"[:_MAX_BRANCH_LEN].rstrip("-/")

    return WorkspaceGuardOutput(
        dirty=bool(porcelain),
        status_tail=_tail(porcelain),
        current_branch=current_branch,
        proposed_branch=proposed,
    )

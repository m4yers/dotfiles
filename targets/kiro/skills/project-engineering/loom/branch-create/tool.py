"""Tool body for the `branch-create` task (loomv2 native contract).

Creates the feature branch approved at branch-gate. On
`decision=abort` it raises, failing the graph so the run surfaces
BLOCKED. `git checkout -b` preserves the working tree, so a
dirty-but-approved workspace carries its changes onto the branch.

The engine loads this module in-process and calls `branch_create`;
all YAML IO and schema validation is engine-owned.
"""

from __future__ import annotations

import subprocess

from io_types import BranchCreateInput, BranchCreateOutput

# Bounded probe for a free branch name suffix.
_MAX_SUFFIX = 100


def _git(workspace: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", workspace, *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _branch_exists(workspace: str, name: str) -> bool:
    return (
        _git(workspace, "rev-parse", "--verify", "--quiet",
             f"refs/heads/{name}").returncode == 0
    )


def branch_create(inp: BranchCreateInput) -> BranchCreateOutput:
    if inp.decision == "abort":
        raise RuntimeError(
            "branch-gate decision was 'abort' — stopping before "
            "implementation (run surfaces BLOCKED)."
        )

    if not inp.proposed_branch:
        # Non-git workspace: nothing to create.
        return BranchCreateOutput(branch="", created=False)

    name = inp.proposed_branch
    if _branch_exists(inp.workspace_abs, name):
        for i in range(2, _MAX_SUFFIX):
            candidate = f"{name}-{i}"
            if not _branch_exists(inp.workspace_abs, candidate):
                name = candidate
                break
        else:
            raise RuntimeError(
                f"could not find a free branch name for {name!r} "
                f"after {_MAX_SUFFIX} attempts"
            )

    checkout = _git(inp.workspace_abs, "checkout", "-b", name)
    if checkout.returncode != 0:
        raise RuntimeError(
            f"git checkout -b {name!r} failed: {checkout.stderr.strip()}"
        )

    return BranchCreateOutput(branch=name, created=True)

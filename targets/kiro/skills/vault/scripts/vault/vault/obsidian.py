"""Wrapper for the Obsidian CLI.

The app must be running. Moving, renaming, or deleting through
Obsidian makes it rewrite wikilinks across the vault — raw ``mv``
does not.

Public surface::

    move(src, dst)
    rename(src, new_name)
    delete(path)

All three raise ``RuntimeError`` if the app is not running, the CLI
reports an error, or the operation times out. The shim deliberately
does NOT fall back to raw ``mv``/``rm`` on failure, because a
filesystem fallback would leave every wikilink pointing at the old
path (see SKILL.md rule 1 and the vault-root ``AGENTS.md``).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from vault.config import (
    OBSIDIAN_CLI,
    OBSIDIAN_OP_TIMEOUT_S,
    OBSIDIAN_POLL_INTERVAL_S,
    VAULT_ROOT,
)
from vault.diff_fm import diff_fm
from vault.pages import abs_path, parse


# Vault name = the leaf directory of VAULT_ROOT. The CLI's
# ``vault=<name>`` option identifies a vault by its display name.
_VAULT_NAME = VAULT_ROOT.name

# The CLI prints these on every call regardless of the command; they
# carry no result and are dropped from returned output and errors.
_CLI_NOISE = (
    "Loading updated app package",
    "Your Obsidian installer is out of date",
)

# The CLI exits 0 even when a command fails; failures are reported
# as output lines with these prefixes.
_CLI_ERROR_PREFIXES = ("Error:", "Vault not found")


def _obsidian_running() -> bool:
    """Best-effort check: is the Obsidian app alive?"""
    try:
        result = subprocess.run(
            ["pgrep", "-x", "Obsidian"],
            # 5s is plenty for pgrep against a single process name on
            # a healthy host; the timeout is there only to prevent a
            # pathological fork/exec hang from stalling the shim and,
            # by extension, the preview gate in SKILL.md.
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _run_cli(*args: str) -> str:
    """Run one Obsidian CLI command against this vault.

    ``args`` are the command and its ``key=value`` options, passed as
    separate argv entries so values with spaces need no quoting.
    Returns the command's output without the CLI's banner lines.
    """
    cmd = [str(OBSIDIAN_CLI), f"vault={_VAULT_NAME}", *args]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=OBSIDIAN_OP_TIMEOUT_S, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"obsidian {args[0]} did not return within "
            f"{OBSIDIAN_OP_TIMEOUT_S}s; wikilinks were NOT "
            f"rewritten.") from e
    except OSError as e:
        raise RuntimeError(f"cannot run {OBSIDIAN_CLI}: {e}") from e

    lines = [
        line for line in (result.stdout + result.stderr).splitlines()
        if line.strip() and not any(n in line for n in _CLI_NOISE)
    ]
    output = "\n".join(lines)
    if result.returncode != 0 or any(
            line.startswith(_CLI_ERROR_PREFIXES) for line in lines):
        raise RuntimeError(
            f"obsidian {' '.join(args)} failed: "
            f"{output or f'exit {result.returncode}'}")
    return output


def _wait_until(predicate, timeout_s: float, poll_s: float) -> bool:
    """Poll ``predicate`` until true or timeout. Returns the final
    result."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(poll_s)
    return predicate()


def _require_running() -> None:
    if not _obsidian_running():
        raise RuntimeError(
            "Obsidian app is not running — start it before "
            "move/rename/delete so wikilinks get rewritten.")


def _capture_baseline(vault_path: str) -> dict:
    """Read frontmatter for the pre-op snapshot."""
    p = abs_path(vault_path)
    if not p.exists():
        return {}
    fm, _ = parse(p.read_text(encoding="utf-8"))
    return fm


def _diff_after(vault_path: str, baseline: dict) -> dict:
    """Compare post-op frontmatter to a pre-op baseline."""
    try:
        return diff_fm(vault_path, baseline=baseline)
    except FileNotFoundError:
        return {
            "changed":  True,
            "baseline": baseline,
            "current":  {},
            "added":    [],
            "removed":  list(baseline.keys()),
            "modified": [],
        }


def _timeout_error(op: str, src: str, dst: str | None = None) -> RuntimeError:
    """Build the uniform error raised when the CLI returned but the
    filesystem never reflected the operation.

    We deliberately do not fall back to a raw filesystem move/delete
    on timeout: raw ``mv``/``rm`` does not rewrite wikilinks, and a
    silent fallback would violate SKILL.md rule 1.
    """
    where = f"{src} -> {dst}" if dst else src
    return RuntimeError(
        f"obsidian {op} did not land on disk within "
        f"{OBSIDIAN_OP_TIMEOUT_S}s ({where}); wikilinks were NOT "
        f"rewritten. Ensure the Obsidian app is running, then retry.")


# ── move ────────────────────────────────────────────────


def _move(op: str, src: str, dst: str) -> dict:
    """Shared body of ``move`` and ``rename``: the CLI's ``move``
    command takes a full destination path, which covers both."""
    _require_running()

    src_abs = abs_path(src)
    if not src_abs.exists():
        raise FileNotFoundError(src)

    baseline = _capture_baseline(src)

    _run_cli("move", f"path={src}", f"to={dst}")

    dst_abs = abs_path(dst)
    settled = _wait_until(
        lambda: dst_abs.exists() and not src_abs.exists(),
        OBSIDIAN_OP_TIMEOUT_S,
        OBSIDIAN_POLL_INTERVAL_S,
    )

    if not settled:
        raise _timeout_error(op, src, dst)

    return {
        "op":               op,
        "src":              src,
        "dst":              dst,
        "obsidian_rewrote": True,
        "fm_diff":          _diff_after(dst, baseline),
    }


def move(src: str, dst: str) -> dict:
    """Move ``src`` → ``dst`` through Obsidian (rewrites
    wikilinks).

    Both paths are vault-relative. Raises ``RuntimeError`` on
    failure rather than falling back to raw filesystem move.
    Returns::

        {
          op:               "move",
          src:              <vault-relative source path>,
          dst:              <vault-relative destination path>,
          obsidian_rewrote: True   (the CLI ran; wikilinks rewritten
                                    by Obsidian, not verified here),
          fm_diff:          <diff_fm envelope: pre-move frontmatter
                             vs. frontmatter now at dst; see
                             vault.diff_fm.diff_fm>,
        }
    """
    return _move("move", src, dst)


# ── rename ──────────────────────────────────────────────


def rename(src: str, new_name: str) -> dict:
    """Rename ``src`` to ``new_name`` within the same folder.

    Raises ``RuntimeError`` on failure rather than falling back to
    raw filesystem rename. Returns the same envelope as ``move``
    with ``op: "rename"`` and ``dst`` set to the new path.
    """
    return _move("rename", src, str(Path(src).with_name(new_name)))


# ── delete ──────────────────────────────────────────────


def delete(path: str) -> dict:
    """Delete ``path`` through Obsidian. The note goes to the trash.

    Raises ``RuntimeError`` on failure rather than falling back to
    raw filesystem delete. Returns::

        {
          op:               "delete",
          path:             <vault-relative path removed>,
          obsidian_rewrote: True,
        }

    No ``fm_diff``: there is no note left to diff.
    """
    _require_running()

    p_abs = abs_path(path)
    if not p_abs.exists():
        raise FileNotFoundError(path)

    _run_cli("delete", f"path={path}")

    settled = _wait_until(
        lambda: not p_abs.exists(),
        OBSIDIAN_OP_TIMEOUT_S,
        OBSIDIAN_POLL_INTERVAL_S,
    )

    if not settled:
        raise _timeout_error("delete", path)

    return {
        "op":               "delete",
        "path":             path,
        "obsidian_rewrote": True,
    }

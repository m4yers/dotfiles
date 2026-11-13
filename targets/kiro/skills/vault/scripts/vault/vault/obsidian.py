"""Wrapper for the Obsidian URL-scheme CLI.

The app must be running. The URL scheme makes Obsidian rewrite
wikilinks across the vault when a note is moved, renamed, or
deleted — raw ``mv`` does not.

Public surface::

    move(src, dst)
    rename(src, new_name)
    delete(path)

All three raise ``RuntimeError`` if the app is not running or the
operation times out. The shim deliberately does NOT fall back to
raw ``mv``/``rm`` on timeout, because a filesystem fallback would
leave every wikilink pointing at the old path (see SKILL.md rule
1 and ``references/vault-rules.md`` — move/rename/delete).
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from urllib.parse import quote

from vault.config import (
    OBSIDIAN_CLI,
    OBSIDIAN_OP_TIMEOUT_S,
    OBSIDIAN_POLL_INTERVAL_S,
    VAULT_ROOT,
)
from vault.diff_fm import diff_fm
from vault.pages import abs_path, parse


# Vault name = the leaf directory of VAULT_ROOT. Obsidian URL
# schemes identify a vault by its display name.
_VAULT_NAME = VAULT_ROOT.name


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


def _invoke_url(url: str) -> None:
    """Hand the URL to Obsidian.

    The app registers itself as the handler for ``obsidian://``
    URLs. On macOS, ``open "<url>"`` is the universal way to invoke
    a URL handler without caring which bundle receives it.
    """
    try:
        subprocess.run(
            ["open", url],
            # 5s is a generous ceiling for open(1) to hand the URL
            # to launchd and return. The actual Obsidian-side work
            # (rewriting wikilinks) is observed via the filesystem
            # polling loop below, not via this call.
            check=True, timeout=5,
            capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"open failed for {url!r}: {e.stderr.strip() or e}"
        ) from e


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
    """Build the uniform timeout error raised by every op.

    We deliberately do not fall back to a raw filesystem move/delete
    on timeout: raw ``mv``/``rm`` does not rewrite wikilinks, and a
    silent fallback would violate SKILL.md rule 1.
    """
    where = f"{src} -> {dst}" if dst else src
    return RuntimeError(
        f"obsidian {op} timed out after {OBSIDIAN_OP_TIMEOUT_S}s "
        f"({where}); wikilinks were NOT rewritten. Ensure the "
        f"Obsidian app is running and the adv-uri plugin is "
        f"installed, then retry.")


# ── move ────────────────────────────────────────────────


def move(src: str, dst: str) -> dict:
    """Move ``src`` → ``dst`` through Obsidian (rewrites
    wikilinks).

    Both paths are vault-relative. Returns an envelope with the
    final path and the pre/post frontmatter diff. Raises
    ``RuntimeError`` on timeout rather than falling back to raw
    filesystem move.
    """
    _require_running()

    src_abs = abs_path(src)
    if not src_abs.exists():
        raise FileNotFoundError(src)

    baseline = _capture_baseline(src)

    url = (
        f"obsidian://advanced-uri"
        f"?vault={quote(_VAULT_NAME)}"
        f"&filepath={quote(src)}"
        f"&filepath2={quote(dst)}"
        f"&commandid=file-explorer%3Amove-file"
    )
    _invoke_url(url)

    dst_abs = abs_path(dst)
    settled = _wait_until(
        lambda: dst_abs.exists() and not src_abs.exists(),
        OBSIDIAN_OP_TIMEOUT_S,
        OBSIDIAN_POLL_INTERVAL_S,
    )

    if not settled:
        raise _timeout_error("move", src, dst)

    return {
        "op":               "move",
        "src":              src,
        "dst":              dst,
        "obsidian_rewrote": True,
        "fm_diff":          _diff_after(dst, baseline),
    }


# ── rename ──────────────────────────────────────────────


def rename(src: str, new_name: str) -> dict:
    """Rename ``src`` to ``new_name`` within the same folder.

    Raises ``RuntimeError`` on timeout rather than falling back to
    raw filesystem rename.
    """
    _require_running()

    src_abs = abs_path(src)
    if not src_abs.exists():
        raise FileNotFoundError(src)

    baseline = _capture_baseline(src)
    dst_rel = str(Path(src).with_name(new_name))

    url = (
        f"obsidian://advanced-uri"
        f"?vault={quote(_VAULT_NAME)}"
        f"&filepath={quote(src)}"
        f"&filename={quote(new_name)}"
        f"&commandid=file-explorer%3Arename-file"
    )
    _invoke_url(url)

    dst_abs = abs_path(dst_rel)
    settled = _wait_until(
        lambda: dst_abs.exists() and not src_abs.exists(),
        OBSIDIAN_OP_TIMEOUT_S,
        OBSIDIAN_POLL_INTERVAL_S,
    )

    if not settled:
        raise _timeout_error("rename", src, dst_rel)

    return {
        "op":               "rename",
        "src":              src,
        "dst":              dst_rel,
        "obsidian_rewrote": True,
        "fm_diff":          _diff_after(dst_rel, baseline),
    }


# ── delete ──────────────────────────────────────────────


def delete(path: str) -> dict:
    """Delete ``path`` through Obsidian (removes wikilinks and
    frontmatter refs across the vault).

    Raises ``RuntimeError`` on timeout rather than falling back to
    raw filesystem delete.
    """
    _require_running()

    p_abs = abs_path(path)
    if not p_abs.exists():
        raise FileNotFoundError(path)

    url = (
        f"obsidian://advanced-uri"
        f"?vault={quote(_VAULT_NAME)}"
        f"&filepath={quote(path)}"
        f"&commandid=app%3Adelete-file"
    )
    _invoke_url(url)

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

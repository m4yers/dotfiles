"""High-level note operations exposed as ``vault read / write /
list / search``.

The ``write`` path is the user-facing one: dry-run returns the
diff the orchestrator shows at the preview gate; a live call runs
``pages.save`` and emits a baseline-vs-current frontmatter diff so
Obsidian rewrites (leading-zero loss, quoting shifts) surface at
the write moment.
"""
from __future__ import annotations

import difflib
import shutil
import subprocess
from pathlib import Path

from vault.config import (
    DEFAULT_SEARCH_FOLDERS,
    VAULT_ROOT,
    VAULT_SEARCH_MAX_RESULTS,
    VAULT_SEARCH_RG_TIMEOUT_S,
)
from vault.diff_fm import diff_fm
from vault.pages import (
    abs_path,
    list_md,
    parse,
    rel_path,
    require_writable,
    save,
    serialize,
)


# ── read ────────────────────────────────────────────────


def read(vault_path: str) -> dict:
    """Return ``{frontmatter, body}`` for an existing page."""
    p = abs_path(vault_path)
    if not p.exists():
        raise FileNotFoundError(vault_path)
    fm, body = parse(p.read_text(encoding="utf-8"))
    return {"frontmatter": fm, "body": body}


# ── write ───────────────────────────────────────────────


def _unified_diff(a: str, b: str, path: str) -> str:
    """Return a short unified diff suitable for a preview gate."""
    diff = difflib.unified_diff(
        a.splitlines(keepends=True),
        b.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        n=3,
    )
    return "".join(diff)


def write(vault_path: str, frontmatter: dict, body: str,
           dry_run: bool = False) -> dict:
    """Create or modify a page.

    ``dry_run=True`` returns the diff without touching disk — the
    preview the orchestrator shows the user.

    On a live write of an existing page, the returned envelope
    includes a ``fm_diff`` block captured by ``diff_fm`` against the
    pre-write frontmatter so Obsidian rewrites surface immediately.

    The zettel exception (``20 ZETTELKASTEN/``) is enforced
    procedurally by the orchestrator, not by this shim.
    """
    require_writable(vault_path)

    p = abs_path(vault_path)
    exists = p.exists()

    before_text = ""
    before_fm: dict = {}
    if exists:
        before_text = p.read_text(encoding="utf-8")
        before_fm, _ = parse(before_text)

    after_text = serialize(frontmatter, body)
    diff = _unified_diff(before_text, after_text, vault_path)

    op = "modified" if exists else "created"

    if dry_run:
        return {
            "op":      op,
            "path":    vault_path,
            "dry_run": True,
            "diff":    diff,
        }

    save(vault_path, frontmatter, body)

    envelope: dict = {
        "op":      op,
        "path":    vault_path,
        "dry_run": False,
        "diff":    diff,
    }
    if exists:
        envelope["fm_diff"] = diff_fm(vault_path, baseline=before_fm)
    return envelope


# ── list ────────────────────────────────────────────────


def list_folder(folder: str) -> list[dict]:
    """List .md files directly under a vault folder."""
    out = []
    for p in list_md(folder):
        st = p.stat()
        out.append({
            "name": p.stem,
            "path": rel_path(p),
            "size": st.st_size,
        })
    return out


# ── search ──────────────────────────────────────────────


def _rg_available() -> bool:
    return shutil.which("rg") is not None


def search(query: str, folders: list[str] | None = None,
            max_results: int = VAULT_SEARCH_MAX_RESULTS) -> list[dict]:
    """Full-text search across one or more top-level vault folders.

    Uses ``ripgrep`` when available (fast + respects .gitignore).
    Falls back to a plain Python scan when ``rg`` is missing so the
    skill still works on a fresh host.

    ``folders`` defaults to every writable + synthesis + zettel
    folder (see ``DEFAULT_SEARCH_FOLDERS``). ``max_results`` is
    capped by ``VAULT_SEARCH_MAX_RESULTS`` (see config.py for the
    rationale).
    """
    folders = list(folders) if folders else list(DEFAULT_SEARCH_FOLDERS)

    # Resolve each folder absolutely; skip ones that do not exist
    # (freshly-created vaults may be missing a folder or two).
    search_dirs: list[Path] = []
    for f in folders:
        p = abs_path(f)
        if p.is_dir():
            search_dirs.append(p)

    if not search_dirs:
        return []

    if _rg_available():
        return _rg_search(query, search_dirs, max_results)
    return _python_search(query, search_dirs, max_results)


def _rg_search(query: str, search_dirs: list[Path],
                max_results: int) -> list[dict]:
    """ripgrep driver. Emits ``[{path, line, excerpt}]``."""
    cmd = [
        "rg",
        "--no-messages",
        "--no-heading",
        "--line-number",
        "--color", "never",
        "--max-count", str(max_results),
        "--glob", "*.md",
        "--ignore-case",
        "--",
        query,
    ] + [str(d) for d in search_dirs]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            # See VAULT_SEARCH_RG_TIMEOUT_S in config.py — 30s is
            # the vault-scan budget before we fall back to the
            # Python scanner, which keeps results flowing on a
            # degraded host rather than failing the whole op.
            timeout=VAULT_SEARCH_RG_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _python_search(query, search_dirs, max_results)

    out: list[dict] = []
    for line in result.stdout.splitlines():
        # ripgrep output: path:line:excerpt
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        abs_match = Path(parts[0])
        try:
            rel = rel_path(abs_match)
        except ValueError:
            continue
        try:
            lineno = int(parts[1])
        except ValueError:
            continue
        out.append({
            "path":    rel,
            "line":    lineno,
            "excerpt": parts[2].strip(),
        })
        if len(out) >= max_results:
            break
    return out


def _python_search(query: str, search_dirs: list[Path],
                    max_results: int) -> list[dict]:
    """Pure-python fallback for hosts without ripgrep."""
    needle = query.lower()
    out: list[dict] = []
    for d in search_dirs:
        for p in d.rglob("*.md"):
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if needle in line.lower():
                    try:
                        rel = rel_path(p)
                    except ValueError:
                        break
                    out.append({
                        "path":    rel,
                        "line":    i,
                        "excerpt": line.strip(),
                    })
                    if len(out) >= max_results:
                        return out
    return out

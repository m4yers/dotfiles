"""High-level note operations exposed as ``vault read / write /
list / search``.

The ``write`` path is the user-facing one: dry-run returns the
diff the orchestrator shows at the preview gate; a live call runs
``pages.save`` and emits a written-vs-on-disk frontmatter diff so
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
           dry_run: bool = False, allow_zettel: bool = False) -> dict:
    """Create or modify a page.

    ``dry_run=True`` returns the diff without touching disk — the
    preview the orchestrator shows the user.

    On a live write, the returned envelope includes a ``fm_diff``
    block captured by ``diff_fm`` against the frontmatter just
    written, so ``changed: true`` means the on-disk frontmatter
    differs from what was written (an unintended rewrite).

    ``20 ZETTELKASTEN/`` is writable only with ``allow_zettel=True``.
    """
    require_writable(vault_path, allow_zettel=allow_zettel)

    p = abs_path(vault_path)
    exists = p.exists()

    before_text = ""
    if exists:
        before_text = p.read_text(encoding="utf-8")

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

    save(vault_path, frontmatter, body, allow_zettel=allow_zettel)

    return {
        "op":      op,
        "path":    vault_path,
        "dry_run": False,
        "diff":    diff,
        "fm_diff": diff_fm(vault_path, baseline=frontmatter),
    }


# ── list ────────────────────────────────────────────────


def list_folder(folder: str) -> list[dict]:
    """List .md files directly under a vault folder.

    Raises ``ValueError`` when ``folder`` is not a directory in the
    vault (via ``pages.list_md``). Returns::

        [
          {
            name: <file stem, i.e. the note title>,
            path: <vault-relative path incl. .md>,
            size: <file size in bytes>,
          },
          ...
        ]
    """
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
    """Full-text literal search across one or more top-level vault
    folders.

    Uses ``ripgrep`` (``-F``) when available; falls back to
    ``grep -rniF --include=*.md`` so both paths match the query as a
    case-insensitive literal string.

    ``folders`` defaults to every writable + synthesis + zettel
    folder (see ``DEFAULT_SEARCH_FOLDERS``); default folders missing
    on disk are skipped, but an explicitly named folder that does
    not exist raises ``ValueError``. ``max_results`` is clamped to
    ``VAULT_SEARCH_MAX_RESULTS`` (see config.py for the rationale)
    and must be at least 1.
    Raises ``RuntimeError`` when the search tool errors or times out.
    """
    if max_results < 1:
        raise ValueError("max_results must be at least 1")
    max_results = min(max_results, VAULT_SEARCH_MAX_RESULTS)

    explicit = bool(folders)
    folders = list(folders) if folders else list(DEFAULT_SEARCH_FOLDERS)

    search_dirs: list[Path] = []
    unknown: list[str] = []
    for f in folders:
        p = abs_path(f)
        if p.is_dir():
            search_dirs.append(p)
        elif explicit:
            unknown.append(f)
    if unknown:
        raise ValueError(
            f"unknown vault folder(s): {', '.join(unknown)}")

    if not search_dirs:
        return []

    if _rg_available():
        cmd = [
            "rg",
            "--no-heading",
            "--line-number",
            "--with-filename",
            "--color", "never",
            "--max-count", str(max_results),
            "--glob", "*.md",
            "--ignore-case",
            "--fixed-strings",
            "--",
            query,
        ]
    else:
        cmd = [
            "grep",
            "-rniF",
            "--include=*.md",
            "-m", str(max_results),
            "--",
            query,
        ]
    return _run_search(cmd + [str(d) for d in search_dirs], max_results)


def _run_search(cmd: list[str], max_results: int) -> list[dict]:
    """Run rg/grep and parse ``path:line:excerpt`` lines into
    ``[{path, line, excerpt}]``. Exit code 1 means no matches;
    2 (or any other non-zero) is an error surfaced with stderr."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            # See VAULT_SEARCH_RG_TIMEOUT_S in config.py.
            timeout=VAULT_SEARCH_RG_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"{cmd[0]} timed out after {VAULT_SEARCH_RG_TIMEOUT_S}s")
    except OSError as e:
        raise RuntimeError(f"{cmd[0]} failed to start: {e}")
    if result.returncode not in (0, 1):
        raise RuntimeError(
            f"{cmd[0]} exited {result.returncode}: "
            f"{result.stderr.strip()}")

    out: list[dict] = []
    for line in result.stdout.splitlines():
        # rg / grep output: path:line:excerpt
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

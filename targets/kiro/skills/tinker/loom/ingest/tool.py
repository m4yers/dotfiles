"""Tool body for the `ingest` task (loomv2 native contract).

Entry task: canonicalises the caller-seeded inputs (slugify the
description, resolve the workspace strictly, echo overrides), then
computes and creates the workspace-intelligence cache directory for
this workspace+commit. Key derivation:

- clean git tree  -> <HEAD>
- dirty git tree  -> <HEAD>-dirty-<sha256(porcelain + NUL + diff)[:12]>
  (stable across invocations for the same uncommitted diff)
- non-git dir     -> nogit-<sha256(name/size/mtime walk)[:12]>

A schema fingerprint (sha256 over every prelude io.yaml) is appended
so bumping any contract auto-invalidates all cached entries. Sibling
dirty entries for the same HEAD older than 24h are pruned on entry.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from io_types import IngestInput, IngestOutput

_CACHE_ROOT = Path("/tmp/tinker-cache")
_LOOM_ROOT = Path.home() / ".kiro" / "skills" / "home" / "tinker" / "loom"

# Prelude tasks whose io.yaml shapes feed the fingerprint.
_PRELUDE_TASKS = [
    "ingest", "code-inventory", "build-detect", "test-detect",
    "dep-analysis", "symbol-index", "code-analysis-plan",
    "file-summary", "workspace-brief",
]

_DIRTY_TTL_SECONDS = 24 * 3600

# Collapse non-alphanumeric runs into single hyphens and trim
# leading/trailing hyphens.
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    return slug or "feature"


def _git(workspace: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", workspace, *args],
        capture_output=True, text=True, errors="replace", timeout=60,
    )


def _schema_fingerprint() -> str:
    h = hashlib.sha256()
    for task in _PRELUDE_TASKS:
        p = _LOOM_ROOT / task / "io.yaml"
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()[:8]


def _nogit_fingerprint(workspace: str) -> str:
    h = hashlib.sha256()
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in sorted(dirs) if not d.startswith(".")]
        for name in sorted(files):
            p = Path(root) / name
            try:
                st = p.stat()
            except OSError:
                continue
            h.update(f"{p}\0{st.st_size}\0{int(st.st_mtime)}\n".encode())
    return h.hexdigest()[:12]


def _workspace_slug(workspace_abs: str) -> str:
    base = Path(workspace_abs).name.lower() or "root"
    digest = hashlib.sha256(workspace_abs.encode()).hexdigest()[:8]
    return f"{base}-{digest}"


def _prune_stale_dirty(slug_dir: Path, head: str) -> None:
    now = time.time()
    for entry in slug_dir.glob(f"{head}-dirty-*"):
        try:
            if now - entry.stat().st_mtime > _DIRTY_TTL_SECONDS:
                import shutil
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            pass


def ingest(inp: IngestInput) -> IngestOutput:
    workspace_abs = str(Path(inp.workspace).expanduser().resolve(strict=True))

    head_proc = _git(workspace_abs, "rev-parse", "HEAD")
    git_head = head_proc.stdout.strip() if head_proc.returncode == 0 else ""
    dirty = False

    if git_head:
        porcelain = _git(
            workspace_abs, "status", "--porcelain=v1",
            "--untracked-files=all",
        ).stdout
        if porcelain.strip():
            dirty = True
            diff = _git(workspace_abs, "diff", "HEAD").stdout
            digest = hashlib.sha256(
                porcelain.encode() + b"\0" + diff.encode()
            ).hexdigest()[:12]
            key = f"{git_head}-dirty-{digest}"
        else:
            key = git_head
    else:
        key = f"nogit-{_nogit_fingerprint(workspace_abs)}"

    key = f"{key}-s{_schema_fingerprint()}"

    cache_dir = ""
    if inp.cache_mode != "bypass":
        slug_dir = _CACHE_ROOT / _workspace_slug(workspace_abs)
        cache_path = slug_dir / key
        cache_path.mkdir(parents=True, exist_ok=True)
        (slug_dir / "files").mkdir(parents=True, exist_ok=True)
        if git_head:
            _prune_stale_dirty(slug_dir, git_head)
        cache_dir = str(cache_path)

    return IngestOutput(
        feature_slug=_slugify(inp.description),
        workspace_abs=workspace_abs,
        description=inp.description,
        build_system_override=inp.build_system_override or "",
        test_system_override=inp.test_system_override or "",
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        cache_dir=cache_dir,
        cache_key=key,
        git_head=git_head,
        dirty=dirty,
        cache_mode=inp.cache_mode or "read-write",
    )

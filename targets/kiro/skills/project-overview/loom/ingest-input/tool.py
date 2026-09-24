"""Tool body for the `ingest` task (loomv2 native contract).

Entry task: canonicalises the caller-seeded inputs (slugify the
description, resolve the workspace strictly, echo overrides), computes
the two identity parts (content + schema) that keyed the cache prefix,
and delegates prefix derivation to the ``cache`` skill via
``cache.sh key``.

Identity parts (ordered):

- Part 1 (content identity):

  - clean git tree   -> ``git:<HEAD>``
  - dirty git tree   -> ``git:<HEAD>:dirty:<sha12(porcelain + NUL + diff)>``
  - non-git tree     -> ``stat:<fp12(name/size/mtime walk)>``

- Part 2 (schema identity):

  - ``schemas:<sha8(ordered bytes of every loom/*/io.yaml)>``

The namespace passed to ``cache.sh key`` is the raw absolute workspace
path — the cache skill slugifies it. The returned prefix has shape
``<namespace-slug>/<fragment-digest>``; the sibling ``blob_prefix`` is
composed as ``<namespace-slug>/files`` so summarise-files blobs sit
outside the fragment (survive commit bumps).

Retention is owned by the cache skill's LRU; this tool creates no
directories and prunes nothing.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from io_types import IngestInputInput, IngestInputOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)
_LOOM_ROOT = (
    Path.home() / ".kiro" / "skills" / "home" / "project-overview" / "loom"
)

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


def _schemas_part() -> str:
    """sha8 over the ordered bytes of every ``loom/*/io.yaml``.

    Sorted by path so ordering is stable across runs. Bumping any
    task's io.yaml (version bump or content edit) flips this part
    and therefore the composed prefix — cache auto-invalidation.
    """
    h = hashlib.sha256()
    for io_yaml in sorted(_LOOM_ROOT.glob("*/io.yaml")):
        h.update(io_yaml.read_bytes())
    return f"schemas:{h.hexdigest()[:8]}"


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


def _content_part(workspace_abs: str) -> tuple[str, str, bool]:
    """Return (content_part, git_head, dirty)."""
    head_proc = _git(workspace_abs, "rev-parse", "HEAD")
    git_head = head_proc.stdout.strip() if head_proc.returncode == 0 else ""
    if git_head:
        porcelain = _git(
            workspace_abs, "status", "--porcelain=v1",
            "--untracked-files=all",
        ).stdout
        if porcelain.strip():
            diff = _git(workspace_abs, "diff", "HEAD").stdout
            sha12 = hashlib.sha256(
                porcelain.encode() + b"\0" + diff.encode()
            ).hexdigest()[:12]
            return f"git:{git_head}:dirty:{sha12}", git_head, True
        return f"git:{git_head}", git_head, False
    fp12 = _nogit_fingerprint(workspace_abs)
    return f"stat:{fp12}", "", False


def _derive_prefix(namespace: str, parts: list[str]) -> str:
    """Delegate `<slug>/<fragment>` composition to `cache.sh key`."""
    argv: list[str] = [str(_CACHE_SH), "key", "--namespace", namespace]
    for p in parts:
        argv.extend(["--part", p])
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=30, check=True,
    )
    return proc.stdout.strip()


def ingest_input(inp: IngestInputInput) -> IngestInputOutput:
    workspace_abs = str(Path(inp.workspace).expanduser().resolve(strict=True))

    content_part, git_head, dirty = _content_part(workspace_abs)
    schemas_part = _schemas_part()

    if inp.cache_mode == "bypass":
        cache_prefix = ""
        blob_prefix = ""
        cache_key = ""
    else:
        cache_prefix = _derive_prefix(
            workspace_abs, [content_part, schemas_part])
        ns_slug, _sep, fragment = cache_prefix.partition("/")
        blob_prefix = f"{ns_slug}/files"
        cache_key = fragment

    return IngestInputOutput(
        feature_slug=_slugify(inp.description),
        workspace_abs=workspace_abs,
        description=inp.description,
        build_system_override=inp.build_system_override or "",
        test_system_override=inp.test_system_override or "",
        captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        cache_prefix=cache_prefix,
        blob_prefix=blob_prefix,
        cache_key=cache_key,
        git_head=git_head,
        dirty=dirty,
        cache_mode=inp.cache_mode or "read-write",
    )

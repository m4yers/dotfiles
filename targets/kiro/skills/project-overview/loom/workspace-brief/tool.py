"""Tool body for the `workspace-brief` task (loomv2 native contract).

Merges the prelude outputs (inventory, dependency map, build/test
resolution, file summaries) into one compact YAML brief consumed by
downstream prompts, writes the brief into the workspace+commit cache
via ``cache.sh set <cache_prefix>/workspace-brief``, and persists
fresh file summaries into the blob-sha-keyed per-file cache under
``<blob_prefix>/<sha>`` (idempotent safety net alongside the
file-summary agent's own writes).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from io_types import WorkspaceBriefInput, WorkspaceBriefOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)
_CACHE_NAME = "workspace-brief"
_BRIEF_BYTE_CAP = 25 * 1024


def _cache_env(cache_mode: str) -> dict:
    return {**os.environ, "CACHE_MODE": cache_mode}


def _cache_set(key: str, cache_mode: str, payload: bytes) -> None:
    """Write raw payload bytes to `<key>` via `cache.sh set` (mode env)."""
    subprocess.run(
        [str(_CACHE_SH), "set", key],
        input=payload, timeout=30, check=False,
        env=_cache_env(cache_mode),
    )


def _persist_file_summaries(blob_prefix: str, cache_mode: str,
                            summaries: list[dict]) -> None:
    """Persist each summary blob under `<blob_prefix>/<sha>` via cache.sh.

    Redundant with the file-summary agent's own writes (same content,
    same key) but kept as a safety net when the agent's blob write is
    skipped or fails. Idempotent — the cache is content-addressed.
    """
    if not blob_prefix:
        return
    for s in summaries:
        sha = s.get("blob_sha")
        if not sha:
            continue
        payload = yaml.safe_dump(
            {"path": s["path"], "purpose": s["purpose"]},
            sort_keys=False,
        ).encode("utf-8")
        _cache_set(f"{blob_prefix}/{sha}", cache_mode, payload)


def workspace_brief(inp: WorkspaceBriefInput) -> WorkspaceBriefOutput:
    fresh = (list(inp.summaries_b1) + list(inp.summaries_b2)
             + list(inp.summaries_b3 or []) + list(inp.summaries_b4 or [])
             + list(inp.summaries_b5 or []) + list(inp.summaries_b6 or []))
    _persist_file_summaries(inp.blob_prefix, inp.cache_mode, fresh)

    file_purposes = sorted(
        ({"path": s["path"], "purpose": s["purpose"]}
         for s in fresh + list(inp.cached_summaries)),
        key=lambda s: s["path"],
    )

    doc = {
        "workspace": inp.workspace_abs,
        "inventory": {
            "total_files": inp.total_files,
            "total_bytes": inp.total_bytes,
            "languages": inp.languages,
            "top_dirs": inp.top_dirs,
            "entrypoints": inp.entrypoints,
        },
        "build": {
            "system": inp.build_system,
            "provenance": inp.build_provenance,
            "fallback_cmd": inp.fallback_build_cmd,
        },
        "test": {
            "system": inp.test_system,
            "fallback_cmd": inp.fallback_test_cmd,
        },
        "dependencies": inp.dependencies,
        "unresolved_imports": inp.unresolved_imports,
        "file_purposes": file_purposes,
        "summarize_mode": inp.summarize_mode,
    }

    brief = yaml.safe_dump(doc, sort_keys=False, width=100)
    while len(brief.encode()) > _BRIEF_BYTE_CAP:
        # Shed the bulkiest sections first, in order.
        if doc["file_purposes"]:
            doc["file_purposes"] = doc["file_purposes"][: len(doc["file_purposes"]) // 2]
        elif len(doc["dependencies"]) > 40:
            doc["dependencies"] = doc["dependencies"][:40]
        elif len(doc["inventory"]["top_dirs"]) > 10:
            doc["inventory"]["top_dirs"] = doc["inventory"]["top_dirs"][:10]
        else:
            break
        brief = yaml.safe_dump(doc, sort_keys=False, width=100)

    if inp.cache_prefix:
        _cache_set(
            f"{inp.cache_prefix}/{_CACHE_NAME}", inp.cache_mode,
            brief.encode("utf-8"),
        )

    return WorkspaceBriefOutput(
        brief=brief,
        file_summaries_total=len(file_purposes),
    )

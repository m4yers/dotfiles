"""Tool body for the ``publish-output`` task (loomv2 native contract).

Exit task: synthesises the compact YAML workspace brief from the
prelude outputs (inventory, dependency map, build/test resolution,
file summaries), persists it (``cache.sh set
<cache_prefix>/workspace-brief``) plus fresh file-summary blobs
(idempotent safety net alongside the summarise-files agent's own
writes), and publishes the flat cross-cutting output contract — the
subgraph's single IO contract. The dataclass constructor fails fast
on any missing field so the subgraph never reports DONE with a
partial output.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

from io_types import PublishOutputInput, PublishOutputOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)
_CACHE_NAME = "workspace-brief"
_BRIEF_BYTE_CAP = 25 * 1024


def _blob_store_dir(blob_prefix: str) -> str:
    """Absolute on-disk directory of the file-summary blob store."""
    root = os.environ.get("CACHE_ROOT", "/tmp/kiro-cache")
    return os.path.join(root, blob_prefix)


def _cache_env(cache_mode: str) -> dict:
    return {**os.environ, "CACHE_MODE": cache_mode}


def _cache_set(key: str, cache_mode: str, payload: bytes) -> None:
    """Write raw payload bytes to `<key>` via `cache.sh set` (mode env)."""
    subprocess.run(
        [str(_CACHE_SH), "set", key],
        input=payload, timeout=30, check=False,
        env=_cache_env(cache_mode),
    )



def publish_output(inp: PublishOutputInput) -> PublishOutputOutput:
    store = _blob_store_dir(inp.blob_prefix)
    try:
        total_summaries = sum(1 for e in os.listdir(store) if e.endswith(".yaml"))
    except OSError:
        total_summaries = 0

    out = {
        "workspace_abs": inp.workspace_abs,
        "feature_slug": inp.feature_slug,
        "description": inp.description,
        "build_system": inp.build_system,
        "build_provenance": inp.build_provenance,
        "build_installed_skills": inp.build_installed_skills,
        "fallback_build_cmd": inp.fallback_build_cmd,
        "test_system": inp.test_system,
        "test_installed_skills": inp.test_installed_skills,
        "fallback_test_cmd": inp.fallback_test_cmd,
        "total_files": inp.total_files,
        "total_bytes": inp.total_bytes,
        "languages": inp.languages,
        "top_dirs": list(inp.top_dirs)[:10],
        "entrypoints": inp.entrypoints,
        "dependencies": list(inp.dependencies)[:40],
        "unresolved_imports": inp.unresolved_imports,
        "summaries_mode": inp.summarize_mode,
        "summaries_total": total_summaries,
        "summaries_store": store,
        "summaries_usage": (
            "One YAML doc per summarised file, keyed by content sha: "
            "<store>/<sha256-of-file>.yaml with fields {path, purpose}. "
            "grep the store by path to look up a file's purpose."
        ),
        "domains": inp.domains,
        "cache_prefix": inp.cache_prefix,
        "blob_prefix": inp.blob_prefix,
        "cache_key": inp.cache_key,
        "git_head": inp.git_head,
        "dirty": inp.dirty,
        "cache_mode": inp.cache_mode,
    }

    # The cached brief doc IS the output; shed list bulk if it ever
    # exceeds the byte cap (unresolved_imports is the only unbounded list).
    brief = yaml.safe_dump(out, sort_keys=False, width=100)
    while len(brief.encode()) > _BRIEF_BYTE_CAP and out["unresolved_imports"]:
        out["unresolved_imports"] = (
            out["unresolved_imports"][: len(out["unresolved_imports"]) // 2])
        brief = yaml.safe_dump(out, sort_keys=False, width=100)

    if inp.cache_prefix:
        _cache_set(
            f"{inp.cache_prefix}/{_CACHE_NAME}", inp.cache_mode,
            brief.encode("utf-8"),
        )

    return PublishOutputOutput(**out)

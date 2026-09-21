"""Tool body for the `workspace-brief` task (loomv2 native contract).

Merges the prelude outputs (inventory, dependency map, build/test
resolution, file summaries) into one compact YAML brief consumed by
downstream prompts, writes the brief into the workspace+commit cache,
and persists fresh file summaries into the blob-sha-keyed per-file
cache so future runs skip those LLM calls.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from io_types import WorkspaceBriefInput, WorkspaceBriefOutput

_CACHE_FILE = "workspace-brief.yaml"
_BRIEF_BYTE_CAP = 25 * 1024


def _persist_file_summaries(cache_dir: str, cache_mode: str,
                            summaries: list[dict]) -> None:
    if not cache_dir or cache_mode not in ("read-write", "write-only"):
        return
    files_dir = Path(cache_dir).parent / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    for s in summaries:
        sha = s.get("blob_sha")
        if not sha:
            continue
        p = files_dir / f"{sha}.yaml"
        if not p.is_file():
            tmp = p.with_suffix(".yaml.tmp")
            tmp.write_text(yaml.safe_dump(
                {"path": s["path"], "purpose": s["purpose"]},
                sort_keys=False))
            tmp.replace(p)


def workspace_brief(inp: WorkspaceBriefInput) -> WorkspaceBriefOutput:
    fresh = (list(inp.summaries_b1) + list(inp.summaries_b2)
             + list(inp.summaries_b3) + list(inp.summaries_b4))
    _persist_file_summaries(inp.cache_dir, inp.cache_mode, fresh)

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

    if inp.cache_dir and inp.cache_mode in ("read-write", "write-only"):
        p = Path(inp.cache_dir) / _CACHE_FILE
        tmp = p.with_suffix(".yaml.tmp")
        tmp.write_text(brief)
        tmp.replace(p)

    return WorkspaceBriefOutput(
        brief=brief,
        file_summaries_total=len(file_purposes),
    )

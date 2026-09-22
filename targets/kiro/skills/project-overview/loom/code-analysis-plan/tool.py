"""Tool body for the `code-analysis-plan` task (loomv2 native contract).

Picks the bounded "hot set" of files worth LLM-summarising and splits
it across 6 fixed fan-out slots. Rules:

- Auto-gate: workspaces with more than 5000 files skip the LLM wave
  entirely (`summarize_mode: skipped-too-large`).
- Hot-set ranking: entrypoints first, then source files by declared
  symbol count and size (bounded to 48 files, 128 KB each).
- Per-file cache: files whose content blob-sha already has a summary
  under the `blob_prefix` (via `cache.sh get <blob_prefix>/<sha>`)
  are surfaced as `cached_summaries` and excluded from batches.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import yaml

from io_types import CodeAnalysisPlanInput, CodeAnalysisPlanOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)

_AUTO_GATE_FILES = 5000
_HOT_SET_MAX = 48
_FILE_BYTE_CAP = 128 * 1024
_BATCH_SLOTS = 6
_SOURCE_LANGS = frozenset(["python", "c", "cpp", "cython", "shell"])


def _blob_sha(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _blob_get(blob_prefix: str, sha: str, cache_mode: str) -> dict | None:
    """Fetch a per-file summary blob from the cache; None on miss."""
    if not blob_prefix or not sha:
        return None
    proc = subprocess.run(
        [str(_CACHE_SH), "get", f"{blob_prefix}/{sha}"],
        capture_output=True, text=True, timeout=30,
        env={**os.environ, "CACHE_MODE": cache_mode},
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        doc = yaml.safe_load(proc.stdout)
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def code_analysis_plan(inp: CodeAnalysisPlanInput) -> CodeAnalysisPlanOutput:
    empty_batches = [{"files": []} for _ in range(_BATCH_SLOTS)]

    if inp.total_files > _AUTO_GATE_FILES:
        return CodeAnalysisPlanOutput(
            summarize_mode="skipped-too-large",
            cached_summaries=[],
            batches=empty_batches,
        )

    try:
        index = yaml.safe_load(Path(inp.symbol_index_path).read_text()) or []
    except (OSError, yaml.YAMLError):
        index = []
    symbols_map = {
        e["path"]: [s["name"] for s in e["symbols"]]
        for e in index
    }
    entry_paths = {e["path"] for e in inp.entrypoints}

    def score(f: dict) -> tuple:
        return (
            f["path"] in entry_paths,
            len(symbols_map.get(f["path"], [])),
            f["bytes"],
        )

    candidates = sorted(
        (f for f in inp.files
         if f["language"] in _SOURCE_LANGS and 0 < f["bytes"] <= _FILE_BYTE_CAP),
        key=score, reverse=True,
    )[:_HOT_SET_MAX]

    ws = Path(inp.workspace_abs)
    cached_summaries: list[dict] = []
    to_summarise: list[dict] = []

    for f in candidates:
        sha = _blob_sha(ws / f["path"])
        if not sha:
            continue
        cached_doc = _blob_get(inp.blob_prefix, sha, inp.cache_mode)
        if cached_doc is not None and "purpose" in cached_doc:
            cached_summaries.append(
                {"path": f["path"], "purpose": cached_doc["purpose"]})
            continue
        to_summarise.append({
            "path": f["path"],
            "blob_sha": sha,
            "symbols": symbols_map.get(f["path"], [])[:10],
        })

    try:
        active = max(1, min(int(inp.max_batches), _BATCH_SLOTS))
    except (TypeError, ValueError):
        active = _BATCH_SLOTS

    if not to_summarise:
        mode = "skipped-empty"
        batches = empty_batches
    else:
        mode = "llm"
        batches = [{"files": to_summarise[i::active] if i < active else []}
                   for i in range(_BATCH_SLOTS)]

    return CodeAnalysisPlanOutput(
        summarize_mode=mode,
        cached_summaries=cached_summaries,
        batches=batches,
    )

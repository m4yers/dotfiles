"""Tool body for the `code-analysis-plan` task (loomv2 native contract).

Picks the bounded "hot set" of files worth LLM-summarising and splits
it across 4 fixed fan-out slots. Rules:

- Auto-gate: workspaces with more than 5000 files skip the LLM wave
  entirely (`summarize_mode: skipped-too-large`).
- Hot-set ranking: entrypoints first, then source files by declared
  symbol count and size (bounded to 48 files, 128 KB each).
- Per-file cache: files whose content blob-sha already has a summary
  under <slug>/files/<sha>.yaml are surfaced as `cached_summaries`
  and excluded from batches.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from io_types import CodeAnalysisPlanInput, CodeAnalysisPlanOutput

_AUTO_GATE_FILES = 5000
_HOT_SET_MAX = 48
_FILE_BYTE_CAP = 128 * 1024
_BATCH_SLOTS = 4
_SOURCE_LANGS = frozenset(["python", "c", "cpp", "cython"])


def _blob_sha(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _files_cache_dir(cache_dir: str) -> Path | None:
    if not cache_dir:
        return None
    return Path(cache_dir).parent / "files"


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
    files_dir = _files_cache_dir(inp.cache_dir)
    cached_summaries: list[dict] = []
    to_summarise: list[dict] = []

    for f in candidates:
        sha = _blob_sha(ws / f["path"])
        if not sha:
            continue
        cache_file = files_dir / f"{sha}.yaml" if files_dir else None
        if (cache_file is not None and inp.cache_mode in ("read-write", "read-only")
                and cache_file.is_file()):
            try:
                doc = yaml.safe_load(cache_file.read_text())
                cached_summaries.append(
                    {"path": f["path"], "purpose": doc["purpose"]})
                continue
            except Exception:
                pass
        to_summarise.append({
            "path": f["path"],
            "blob_sha": sha,
            "symbols": symbols_map.get(f["path"], [])[:10],
        })

    if not to_summarise:
        mode = "skipped-empty"
        batches = empty_batches
    else:
        mode = "llm"
        batches = [{"files": to_summarise[i::_BATCH_SLOTS]}
                   for i in range(_BATCH_SLOTS)]

    return CodeAnalysisPlanOutput(
        summarize_mode=mode,
        cached_summaries=cached_summaries,
        batches=batches,
    )

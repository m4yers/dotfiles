"""Tool body for the `plan-code-analysis` task (loomv2 native contract).

Picks the bounded "hot set" of files worth LLM-summarising and splits
it across 6 fixed fan-out slots. Rules:

- Auto-gate: workspaces with more than 5000 files skip the LLM wave
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

from io_types import PlanCodeAnalysisInput, PlanCodeAnalysisOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)

_BATCH_SLOTS = 30
# Per-batch caps: one summarise agent reads its whole batch in a single
# batched call, so cumulative bytes are bounded by the agent's context
# window (~400 KiB ≈ 100k tokens leaves room for prompt + generation);
# the file-count cap guards the degenerate many-tiny-files batch.
_BATCH_BYTE_CAP = 256 * 1024
# Agents read at most 250 lines per file, so a file's context cost is
# capped regardless of its on-disk size; packing charges each file
# min(bytes, _READ_BYTE_CEIL) against the byte cap.
_READ_BYTE_CEIL = 12 * 1024
_BATCH_FILE_CAP = 60
# cached_summaries is graph payload (feeds the brief, which sheds
# aggressively anyway) — report only the top-ranked slice.
_CACHED_REPORT_CAP = 500


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
    """Fetch a per-file summary blob; None on miss.

    Reads the cache value file directly (documented layout:
    `<KIRO_CACHE_ROOT>/<key>.yaml`) instead of spawning `cache.sh get`
    per file — this probe runs once per candidate (potentially tens of
    thousands), where subprocess startup would dominate the task.
    """
    if not blob_prefix or not sha:
        return None
    if cache_mode not in ("read-write", "read-only"):
        return None
    root = Path(os.environ.get("KIRO_CACHE_ROOT", "/tmp/kiro-cache"))
    path = root / blob_prefix / f"{sha}.yaml"
    if not path.is_file():
        return None
    try:
        doc = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError):
        return None
    return doc if isinstance(doc, dict) else None


def _pack_batches(files: list[dict], active: int) -> list[dict]:
    """First-fit pack `files` (ranked order) into `active` batches.

    A batch closes when adding a file would exceed _BATCH_BYTE_CAP
    cumulative bytes or _BATCH_FILE_CAP entries; files that fit no
    open batch are deferred to the next run. `bytes` is packing-only
    transport and stripped from the emitted entries.
    """
    bins = [{"bytes": 0, "files": []} for _ in range(active)]
    for f in files:
        size = min(f.get("bytes") or 0, _READ_BYTE_CEIL)
        for b in bins:
            if b["files"] and (b["bytes"] + size > _BATCH_BYTE_CAP
                               or len(b["files"]) >= _BATCH_FILE_CAP):
                continue
            b["files"].append({k: v for k, v in f.items() if k != "bytes"})
            b["bytes"] += size
            break
    return [{"files": b["files"]} for b in bins] + \
        [{"files": []} for _ in range(_BATCH_SLOTS - active)]


def plan_code_analysis(inp: PlanCodeAnalysisInput) -> PlanCodeAnalysisOutput:
    empty_batches = [{"files": []} for _ in range(_BATCH_SLOTS)]

    try:
        index = yaml.safe_load(Path(inp.index_symbols_path).read_text()) or []
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

    try:
        budget = max(1, int(inp.summary_budget))
    except (TypeError, ValueError):
        budget = 240
    try:
        all_candidates = yaml.safe_load(
            Path(inp.candidates_path).read_text()) or []
    except OSError:
        all_candidates = []
    # Re-rank with symbol counts (richer signal than inventory's
    # size-only ranking). The budget is applied to UNCACHED files
    # below — not here — so coverage converges across runs instead of
    # stalling once the top-ranked files are all cached.
    # Policy: only non-test engine code is summarised. Test files
    # (classified by inventory-code's is_test flag) are excluded from
    # both batching and the cached report.
    candidates = sorted(
        (f for f in all_candidates if not f.get("is_test")),
        key=score, reverse=True)

    ws = Path(inp.workspace_abs)
    cached_summaries: list[dict] = []
    to_summarise: list[dict] = []

    for f in candidates:
        sha = _blob_sha(ws / f["path"])
        if not sha:
            continue
        cached_doc = _blob_get(inp.blob_prefix, sha, inp.cache_mode)
        if cached_doc is not None and "purpose" in cached_doc:
            if len(cached_summaries) < _CACHED_REPORT_CAP:
                cached_summaries.append(
                    {"path": f["path"], "purpose": cached_doc["purpose"]})
            continue
        if len(to_summarise) >= budget:
            continue  # this run's budget consumed; rest waits for next run
        to_summarise.append({
            "path": f["path"],
            "blob_sha": sha,
            "bytes": int(f.get("bytes") or 0),
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
        batches = _pack_batches(to_summarise, active)

    return PlanCodeAnalysisOutput(
        summarize_mode=mode,
        cached_summaries=cached_summaries,
        batches=batches,
    )

"""Tool body for the `code-inventory` task (loomv2 native contract).

Fast workspace map: file enumeration via `git ls-files -oc
--exclude-standard -z` (os.walk fallback for non-git dirs), static
extension->language mapping, streaming LOC counts with a byte-based
estimate for files over 512 KB, top-dirs rollup, and heuristic
entrypoint detection. Results cached per workspace+commit.
"""

from __future__ import annotations

import os
import subprocess
from collections import defaultdict
from pathlib import Path

import yaml

from io_types import CodeInventoryInput, CodeInventoryOutput

_CACHE_FILE = "code-inventory.yaml"
_MAX_FILES = 100000
_MAX_CANDIDATES = 2000
_CANDIDATE_BYTE_CAP = 128 * 1024
_SOURCE_LANGS = frozenset(["python", "c", "cpp", "cython"])
_BIG_FILE_BYTES = 512 * 1024
_AVG_LINE_LEN = 35

# Extensions always treated as text even though unmapped to a language.
_TEXT_EXTS = frozenset([
    ".txt", ".cfg", ".ini", ".in", ".rst", ".xml", ".html", ".css",
    ".sql", ".proto", ".cmake", ".mk", ".am", ".ac", ".m4", ".gradle",
    ".properties", ".env", ".template", ".j2", ".jinja", ".tpl",
    ".csv", ".tsv", ".patch", ".diff", ".spec", ".service", ".conf",
])

_EXT_LANG = {
    ".py": "python", ".pyi": "python", ".pyx": "cython", ".pxd": "cython",
    ".c": "c", ".h": "c",
    ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hxx": "cpp", ".hh": "cpp",
    ".sh": "shell", ".bash": "shell",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json", ".toml": "toml",
    ".md": "markdown", ".rst": "markdown",
    ".sql": "sql", ".cmake": "cmake",
}


def _read_cache(cache_dir: str, cache_mode: str) -> dict | None:
    if not cache_dir or cache_mode not in ("read-write", "read-only"):
        return None
    p = Path(cache_dir) / _CACHE_FILE
    if p.is_file():
        try:
            return yaml.safe_load(p.read_text())
        except Exception:
            return None
    return None


def _write_cache(cache_dir: str, cache_mode: str, doc: dict) -> None:
    if not cache_dir or cache_mode not in ("read-write", "write-only"):
        return
    p = Path(cache_dir) / _CACHE_FILE
    tmp = p.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(doc, sort_keys=False))
    tmp.replace(p)


def _is_text(path: Path, suffix: str) -> bool:
    """Cheap binary sniff: known extensions pass; unknowns must have
    no NUL byte in the first 8 KB."""
    if suffix in _EXT_LANG or suffix in _TEXT_EXTS:
        return True
    try:
        with path.open("rb") as fh:
            return b"\0" not in fh.read(8192)
    except OSError:
        return False


def _enumerate(workspace: str) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", workspace, "ls-files", "-oc",
         "--exclude-standard", "-z"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode == 0:
        return [p for p in proc.stdout.split("\0") if p]
    out: list[str] = []
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_root = os.path.relpath(root, workspace)
        for name in files:
            out.append(name if rel_root == "." else f"{rel_root}/{name}")
            if len(out) >= _MAX_FILES:
                return out
    return out


def _count_loc(path: Path, size: int) -> int:
    if size > _BIG_FILE_BYTES:
        return size // _AVG_LINE_LEN
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _entrypoints(workspace: Path, files: list[dict]) -> list[dict]:
    hits: list[dict] = []
    for f in files:
        p = f["path"]
        name = p.rsplit("/", 1)[-1]
        if name == "__main__.py":
            hits.append({"path": p, "kind": "python-main"})
        elif name in ("main.py", "cli.py", "app.py") and f["language"] == "python":
            hits.append({"path": p, "kind": "python-entry-guess"})
        elif name in ("main.c", "main.cc", "main.cpp"):
            hits.append({"path": p, "kind": "cpp-main"})
    # pyproject console scripts
    pyproject = workspace / "pyproject.toml"
    if pyproject.is_file():
        try:
            import tomllib
            doc = tomllib.load(pyproject.open("rb"))
            for name in (doc.get("project", {}).get("scripts") or {}):
                hits.append({"path": "pyproject.toml", "kind": f"console-script:{name}"})
        except Exception:
            pass
    return hits[:20]


def code_inventory(inp: CodeInventoryInput) -> CodeInventoryOutput:
    cached = _read_cache(inp.cache_dir, inp.cache_mode)
    if cached is not None:
        cached["cache_hit"] = True
        return CodeInventoryOutput.from_dict(cached)

    ws = Path(inp.workspace_abs)
    rel_paths = _enumerate(inp.workspace_abs)[:_MAX_FILES]

    files: list[dict] = []
    lang_stat: dict[str, dict] = defaultdict(lambda: {"files": 0, "loc": 0, "bytes": 0})
    dir_stat: dict[str, dict] = defaultdict(lambda: {"files": 0, "bytes": 0})
    total_bytes = 0

    for rel in rel_paths:
        p = ws / rel
        try:
            size = p.stat().st_size
        except OSError:
            continue
        suffix = Path(rel).suffix.lower()
        if not _is_text(p, suffix):
            continue  # skip binaries and non-text files entirely
        lang = _EXT_LANG.get(suffix, "other")
        files.append({"path": rel, "bytes": size, "language": lang})
        total_bytes += size
        s = lang_stat[lang]
        s["files"] += 1
        s["bytes"] += size
        if lang in ("python", "c", "cpp", "cython", "shell", "cmake", "sql"):
            s["loc"] += _count_loc(p, size)
        parts = rel.split("/")
        for depth in (1, 2):
            if len(parts) > depth:
                d = dir_stat["/".join(parts[:depth])]
                d["files"] += 1
                d["bytes"] += size

    languages = [
        {"language": k, **v}
        for k, v in sorted(lang_stat.items(), key=lambda kv: -kv[1]["bytes"])
    ]
    top_dirs = [
        {"path": k, **v}
        for k, v in sorted(dir_stat.items(), key=lambda kv: -kv[1]["bytes"])[:20]
    ]

    entrypoints = _entrypoints(ws, files)
    entry_paths = {e["path"] for e in entrypoints}
    candidates = sorted(
        (f for f in files
         if f["language"] in _SOURCE_LANGS
         and 0 < f["bytes"] <= _CANDIDATE_BYTE_CAP),
        key=lambda f: (f["path"] in entry_paths, f["bytes"]),
        reverse=True,
    )[:_MAX_CANDIDATES]

    doc = {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "languages": languages,
        "top_dirs": top_dirs,
        "entrypoints": entrypoints,
        "candidate_files": candidates,
        "cache_hit": False,
    }
    _write_cache(inp.cache_dir, inp.cache_mode, doc)
    return CodeInventoryOutput.from_dict(doc)

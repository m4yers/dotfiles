"""Tool body for the `inventory-code` task (loomv2 native contract).

Fast workspace map: file enumeration via `git ls-files -oc
--exclude-standard -z` (os.walk fallback for non-git dirs), static
extension->language mapping, streaming LOC counts with a byte-based
estimate for files over 512 KB, top-dirs rollup, and heuristic
entrypoint detection. Results cached via the `cache` skill under
`<cache_prefix>/inventory-code`.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

import yaml

from io_types import InventoryCodeInput, InventoryCodeOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)
_CACHE_NAME = "inventory-code"

_MAX_FILES = 100000
_CANDIDATE_BYTE_CAP = 128 * 1024
_SOURCE_LANGS = frozenset(["python", "c", "cpp", "cython", "shell"])
_BIG_FILE_BYTES = 512 * 1024

# Test classification: standard path segments + basename patterns.
# Generic across projects; test FRAMEWORK code without these markers
# deliberately classifies as non-test (it is maintained code too).
_TEST_DIR_SEGMENTS = frozenset([
    "test", "tests", "testing", "unit_tests", "integration_tests",
    "gtest", "cppunit", "spec", "specs", "mocks", "fixtures",
    "testdata", "__tests__",
])
_TEST_BASENAME_RE = re.compile(
    r"^(test_|conftest\.py$)|(_tests?\.[A-Za-z0-9]+$)|(\.spec\.[A-Za-z0-9]+$)")

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


def _cache_env(cache_mode: str) -> dict:
    return {**os.environ, "CACHE_MODE": cache_mode}


def _cache_get(cache_prefix: str, cache_mode: str) -> dict | None:
    if not cache_prefix:
        return None
    proc = subprocess.run(
        [str(_CACHE_SH), "get", f"{cache_prefix}/{_CACHE_NAME}"],
        capture_output=True, text=True, timeout=30,
        env=_cache_env(cache_mode),
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        doc = yaml.safe_load(proc.stdout)
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def _cache_set(cache_prefix: str, cache_mode: str, doc: dict) -> None:
    if not cache_prefix:
        return
    subprocess.run(
        [str(_CACHE_SH), "set", f"{cache_prefix}/{_CACHE_NAME}"],
        input=yaml.safe_dump(doc, sort_keys=False),
        text=True, timeout=30, check=False,
        env=_cache_env(cache_mode),
    )


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


def _store_candidates(cache_prefix: str, cache_mode: str,
                      workspace_abs: str, candidates: list[dict]) -> str:
    """Store the ranked candidate list as a cache side document
    (`<cache_prefix>/candidates`); return its on-disk path. Bypass /
    blocked writes fall back to a stable per-workspace temp file so
    repeated runs overwrite instead of leaking.
    """
    import hashlib
    payload = yaml.safe_dump(candidates, sort_keys=False).encode("utf-8")
    if cache_prefix:
        key = f"{cache_prefix}/candidates"
        subprocess.run(
            [str(_CACHE_SH), "set", key],
            input=payload, timeout=60, check=False,
            env=_cache_env(cache_mode),
        )
        root = Path(os.environ.get("KIRO_CACHE_ROOT", "/tmp/kiro-cache"))
        path = root / f"{key}.yaml"
        if path.is_file():
            return str(path)
    h = hashlib.sha256(workspace_abs.encode()).hexdigest()[:8]
    d = Path(f"/tmp/project-overview-candidates-{h}")
    d.mkdir(parents=True, exist_ok=True)
    path = d / "candidates.yaml"
    tmp = path.with_suffix(".yaml.tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)
    return str(path)


def _is_test_path(path: str) -> bool:
    parts = path.lower().split("/")
    if any(seg in _TEST_DIR_SEGMENTS for seg in parts[:-1]):
        return True
    return bool(_TEST_BASENAME_RE.search(parts[-1]))


def inventory_code(inp: InventoryCodeInput) -> InventoryCodeOutput:
    cached = _cache_get(inp.cache_prefix, inp.cache_mode)
    if cached is not None:
        cached["cache_hit"] = True
        return InventoryCodeOutput.from_dict(cached)

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
    # ALL qualifying candidates, ranked (entrypoints first, then size).
    # The list is bulk data: it goes to the cache as a side document and
    # only its path + count cross the graph.
    candidates = sorted(
        ({**f, "is_test": _is_test_path(f["path"])} for f in files
         if f["language"] in _SOURCE_LANGS
         and 0 < f["bytes"] <= _CANDIDATE_BYTE_CAP),
        key=lambda f: (f["path"] in entry_paths, f["bytes"]),
        reverse=True,
    )
    candidates_path = _store_candidates(
        inp.cache_prefix, inp.cache_mode, inp.workspace_abs, candidates)

    doc = {
        "total_files": len(files),
        "total_bytes": total_bytes,
        "languages": languages,
        "top_dirs": top_dirs,
        "entrypoints": entrypoints,
        "candidates_path": candidates_path,
        "candidates_total": len(candidates),
        "cache_hit": False,
    }
    _cache_set(inp.cache_prefix, inp.cache_mode, doc)
    return InventoryCodeOutput.from_dict(doc)

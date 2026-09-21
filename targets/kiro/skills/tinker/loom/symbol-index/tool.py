"""Tool body for the `symbol-index` task (loomv2 native contract).

Per-file declared symbols (classes, functions) for Python and C/C++,
FULL coverage — every source file, recomputed on every run (ctags
parses even multi-million-LOC trees in seconds, so symbol data is
never cached). The full index is written to disk and only its path
crosses the graph; consumers (code-analysis-plan) read it directly.

Tiered backends, best available wins:

1. universal-ctags (`--output-format=json`) — streaming JSON lines.
   When missing, one non-interactive package-manager install attempt
   (sudo -n) is made before falling through.
2. Exuberant ctags (`-x` cross-reference lines).
3. Pure-Python regex over class/def and C/C++ function definitions
   (bounded fallback).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

import yaml

from io_types import SymbolIndexInput, SymbolIndexOutput

_INDEX_FILE = "symbol-index-full.yaml"
_MAX_FILES = 100000          # safety bound only
_MAX_SYMBOLS_PER_FILE = 50
_LANG_ARGS = ["--languages=Python,C,C++"]
_KINDS_KEEP = frozenset(["class", "function", "member", "struct", "f", "c", "s", "m"])


_SOURCE_EXTS = (".py", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx")


def _list_source_files(ws: str) -> list[str]:
    """Bounded source-file list (git ls-files, os.walk fallback)."""
    try:
        proc = subprocess.run(
            ["git", "-C", ws, "ls-files", "-oc", "--exclude-standard", "-z"],
            capture_output=True, text=True, errors="replace", timeout=120,
        )
        entries = [e for e in proc.stdout.split("\0") if e] \
            if proc.returncode == 0 else []
    except (subprocess.TimeoutExpired, OSError):
        entries = []
    if not entries:
        root = Path(ws)
        entries = []
        for q in root.rglob("*"):
            if len(entries) >= _MAX_FILES * 4:
                break
            if q.is_file():
                rel = q.relative_to(root)
                if not any(part.startswith(".") for part in rel.parts):
                    entries.append(str(rel))
    out = [e for e in entries if e.lower().endswith(_SOURCE_EXTS)]
    return out[:_MAX_FILES]


def _ctags_is_universal() -> bool:
    ctags = shutil.which("ctags")
    if not ctags:
        return False
    try:
        head = subprocess.run([ctags, "--version"], capture_output=True,
                              text=True, timeout=10).stdout
    except (subprocess.TimeoutExpired, OSError):
        return False
    return "Universal Ctags" in head


def _try_install_universal_ctags() -> bool:
    pm = shutil.which("dnf") or shutil.which("yum") or shutil.which("apt-get")
    if pm is None:
        return False
    for pkg in ("universal-ctags", "ctags-universal"):
        subprocess.run(["sudo", "-n", pm, "install", "-y", pkg],
                       capture_output=True, timeout=120)
        if _ctags_is_universal():
            return True
    return False


def _run_ctags_json(ws: str, files: list[str]) -> dict[str, list[dict]] | None:
    if not files:
        return {}
    try:
        proc = subprocess.run(
            ["ctags", "-L", "-", "-f", "-", "--output-format=json",
             *_LANG_ARGS],
            cwd=ws, input="\n".join(files), capture_output=True,
            text=True, errors="replace", timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    by_file: dict[str, list[dict]] = defaultdict(list)
    for line in proc.stdout.splitlines():
        try:
            tag = json.loads(line)
        except json.JSONDecodeError:
            continue
        if tag.get("_type") != "tag" or tag.get("kind") not in _KINDS_KEEP:
            continue
        path = tag.get("path", "").lstrip("./")
        if len(by_file[path]) < _MAX_SYMBOLS_PER_FILE:
            by_file[path].append({"name": tag["name"], "kind": tag["kind"]})
    return by_file


def _run_ctags_classic(ws: str, files: list[str]) -> dict[str, list[dict]] | None:
    if not files:
        return {}
    try:
        proc = subprocess.run(
            ["ctags", "-L", "-", "-x", *_LANG_ARGS],
            cwd=ws, input="\n".join(files), capture_output=True,
            text=True, errors="replace", timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    by_file: dict[str, list[dict]] = defaultdict(list)
    # -x line: NAME KIND LINE FILE SOURCE...
    for line in proc.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        name, kind, _line, path = parts[0], parts[1], parts[2], parts[3]
        if kind not in _KINDS_KEEP:
            continue
        path = path.lstrip("./")
        if len(by_file[path]) < _MAX_SYMBOLS_PER_FILE:
            by_file[path].append({"name": name, "kind": kind})
    return by_file


_PY_SYMBOL = re.compile(r"^(?:class|def)\s+([A-Za-z_]\w*)", re.M)
_CPP_SYMBOL = re.compile(
    r"^(?:class|struct)\s+([A-Za-z_]\w*)|^[A-Za-z_][\w:<>*& ]*?\b([A-Za-z_]\w*)\s*\([^;]*\)\s*\{",
    re.M,
)


def _run_regex(ws: str) -> dict[str, list[dict]]:
    by_file: dict[str, list[dict]] = defaultdict(list)
    root = Path(ws)
    count = 0
    for p in root.rglob("*"):
        if count >= _MAX_FILES:
            break
        if not p.is_file():
            continue
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            continue
        suffix = p.suffix.lower()
        if suffix == ".py":
            regex, kind = _PY_SYMBOL, "function"
        elif suffix in (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"):
            regex, kind = _CPP_SYMBOL, "function"
        else:
            continue
        count += 1
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        rel = str(p.relative_to(root))
        for m in regex.finditer(text):
            name = m.group(1) or (m.group(2) if m.lastindex and m.lastindex > 1 else None)
            if not name:
                continue
            if len(by_file[rel]) < _MAX_SYMBOLS_PER_FILE:
                by_file[rel].append({"name": name, "kind": kind})
    return by_file


def symbol_index(inp: SymbolIndexInput) -> SymbolIndexOutput:
    by_file: dict[str, list[dict]] | None = None
    tool = "regex"
    files = _list_source_files(inp.workspace_abs)

    if _ctags_is_universal() or _try_install_universal_ctags():
        by_file = _run_ctags_json(inp.workspace_abs, files)
        tool = "ctags-json"
    if by_file is None and shutil.which("ctags"):
        by_file = _run_ctags_classic(inp.workspace_abs, files)
        tool = "ctags-classic"
    if by_file is None:
        by_file = _run_regex(inp.workspace_abs)
        tool = "regex"

    symbols_by_file = [
        {"path": path, "symbols": syms}
        for path, syms in sorted(by_file.items())
    ]

    if inp.cache_dir:
        index_dir = Path(inp.cache_dir)
    else:
        import tempfile
        index_dir = Path(tempfile.mkdtemp(prefix="tinker-symbols-"))
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / _INDEX_FILE
    tmp = index_path.with_suffix(".yaml.tmp")
    tmp.write_text(yaml.safe_dump(symbols_by_file, sort_keys=False))
    tmp.replace(index_path)

    return SymbolIndexOutput(
        index_path=str(index_path),
        files_indexed=len(symbols_by_file),
        symbols_total=sum(len(e["symbols"]) for e in symbols_by_file),
        tags_tool=tool,
    )

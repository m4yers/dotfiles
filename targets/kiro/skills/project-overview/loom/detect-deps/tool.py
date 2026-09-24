"""Tool body for the `detect-deps` task (loomv2 native contract).

Two cheap passes:

1. Manifest parse — pyproject.toml (project.dependencies,
   optional-dependencies, dependency-groups, tool.poetry),
   requirements*.txt, setup.cfg, plus regexes over CMakeLists.txt,
   configure.ac, meson.build, and Makefile for C/C++ library deps.
2. Usage map — one batched search per language family mapping each
   dep name to up to 10 files that import/include it. Search tiers:
   rg -> git grep -> pure-Python re walk. When `rg` is absent the
   tool makes a single non-interactive package-manager install
   attempt (sudo -n; never blocks) before falling back.

Also reports top-level imports with no manifest entry. Cached via the
`cache` skill under `<cache_prefix>/detect-deps`.
"""

from __future__ import annotations

import configparser
import os
import re
import shutil
import subprocess
import tomllib
from collections import defaultdict
from pathlib import Path

import yaml

from io_types import DetectDepsInput, DetectDepsOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)
_CACHE_NAME = "detect-deps"

_MAX_DEPS = 200
_MAX_UNRESOLVED = 40
_MAX_USED_IN = 10

# Python stdlib top-level names we never flag as unresolved.
_STDLIB_HINT = frozenset(
    "os sys re json math time typing pathlib subprocess collections "
    "itertools functools dataclasses abc io enum logging unittest "
    "tempfile shutil hashlib datetime argparse contextlib copy csv "
    "threading multiprocessing socket struct signal traceback types "
    "warnings weakref pickle random string textwrap tomllib urllib "
    "http html xml email base64 binascii bisect heapq queue select "
    "sqlite3 ssl statistics uuid zlib gzip tarfile zipfile glob "
    "fnmatch stat platform getpass pwd grp errno ctypes array".split()
)


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


def _try_install(binary: str, packages: list[str]) -> bool:
    """One-shot, non-interactive package-manager install attempt."""
    pm = shutil.which("dnf") or shutil.which("yum") or shutil.which("apt-get")
    if pm is None:
        return False
    for pkg in packages:
        subprocess.run(
            ["sudo", "-n", pm, "install", "-y", pkg],
            capture_output=True, timeout=120,
        )
        if shutil.which(binary):
            return True
    return False


# ---------------------------------------------------------------------------
# Pass 1: manifests
# ---------------------------------------------------------------------------

_PEP508_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$")


def _split_pep508(entry: str) -> tuple[str, str]:
    m = _PEP508_NAME.match(entry)
    if not m:
        return entry.strip(), ""
    return m.group(1), m.group(2).strip().rstrip(",")


def _parse_python_manifests(ws: Path) -> list[dict]:
    deps: list[dict] = []
    pyproject = ws / "pyproject.toml"
    if pyproject.is_file():
        try:
            doc = tomllib.load(pyproject.open("rb"))
        except (OSError, tomllib.TOMLDecodeError):
            doc = {}
        for entry in doc.get("project", {}).get("dependencies", []) or []:
            name, spec = _split_pep508(str(entry))
            deps.append({"name": name, "spec": spec, "scope": "runtime",
                         "origin": "pyproject.toml:[project.dependencies]"})
        for group, entries in (doc.get("project", {})
                               .get("optional-dependencies", {}) or {}).items():
            for entry in entries:
                name, spec = _split_pep508(str(entry))
                deps.append({"name": name, "spec": spec, "scope": "dev",
                             "origin": f"pyproject.toml:[optional.{group}]"})
        for group, entries in (doc.get("dependency-groups", {}) or {}).items():
            for entry in entries:
                if not isinstance(entry, str):
                    continue
                name, spec = _split_pep508(entry)
                deps.append({"name": name, "spec": spec, "scope": "dev",
                             "origin": f"pyproject.toml:[dependency-groups.{group}]"})
        poetry = doc.get("tool", {}).get("poetry", {}).get("dependencies", {})
        for name, spec in (poetry or {}).items():
            if name.lower() == "python":
                continue
            deps.append({"name": name, "spec": str(spec), "scope": "runtime",
                         "origin": "pyproject.toml:[tool.poetry.dependencies]"})
    for req in sorted(ws.glob("requirements*.txt")):
        try:
            for line in req.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith(("#", "-")):
                    continue
                name, spec = _split_pep508(line)
                deps.append({"name": name, "spec": spec, "scope": "runtime",
                             "origin": req.name})
        except OSError:
            pass
    setup_cfg = ws / "setup.cfg"
    if setup_cfg.is_file():
        cp = configparser.ConfigParser()
        try:
            cp.read(setup_cfg)
            for line in cp.get("options", "install_requires",
                               fallback="").splitlines():
                line = line.strip()
                if line:
                    name, spec = _split_pep508(line)
                    deps.append({"name": name, "spec": spec, "scope": "runtime",
                                 "origin": "setup.cfg:[options]"})
        except configparser.Error:
            pass
    return deps


_CPP_PATTERNS = [
    ("CMakeLists.txt", re.compile(r"find_package\(\s*(\w+)"), "cmake find_package"),
    ("CMakeLists.txt", re.compile(r"pkg_check_modules\(\w+\s+([^\)\s]+)"), "cmake pkg_check_modules"),
    ("configure.ac",   re.compile(r"AC_CHECK_LIB\(\[?(\w+)"), "autoconf AC_CHECK_LIB"),
    ("meson.build",    re.compile(r"dependency\(\s*['\"]([^'\"]+)"), "meson dependency"),
    ("Makefile",       re.compile(r"-l(\w+)"), "Makefile -l"),
]


def _parse_cpp_manifests(ws: Path) -> list[dict]:
    deps: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for filename, pattern, kind in _CPP_PATTERNS:
        p = ws / filename
        if not p.is_file():
            continue
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        for m in pattern.finditer(text):
            name = m.group(1)
            if (filename, name) in seen:
                continue
            seen.add((filename, name))
            deps.append({"name": name, "spec": "", "scope": "runtime",
                         "origin": f"{filename} ({kind})"})
    return deps


# ---------------------------------------------------------------------------
# Pass 2: usage map
# ---------------------------------------------------------------------------

_PY_IMPORT = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
_CPP_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^/><"]+)', re.M)


def _collect_imports(ws: Path) -> tuple[dict[str, list[str]], str]:
    """Map top-level import/include name -> files, via the best tier."""
    usage: dict[str, list[str]] = defaultdict(list)

    def _record(pattern_kind: str, path: str, name: str) -> None:
        name = name.split(".")[0].strip()
        if not name:
            return
        if pattern_kind == "py" and name in _STDLIB_HINT:
            return
        if len(usage[name]) < _MAX_USED_IN * 4 and path not in usage[name]:
            usage[name].append(path)

    rg = shutil.which("rg")
    if rg is None and _try_install("rg", ["ripgrep"]):
        rg = shutil.which("rg")

    if rg:
        tool = "rg"
        cmds = [
            ("py", [rg, "-n", "--no-heading", "-g", "*.py",
                    r"^\s*(import|from)\s+\w+", str(ws)]),
            ("cpp", [rg, "-n", "--no-heading", "-g", "*.{c,cc,cpp,cxx,h,hpp,hxx}",
                     r"^\s*#\s*include", str(ws)]),
        ]
    elif subprocess.run(
            ["git", "-C", str(ws), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True).stdout.strip() == "true":
        tool = "git-grep"
        cmds = [
            ("py", ["git", "-C", str(ws), "grep", "-nIE",
                    r"^\s*(import|from)\s+\w+", "--", "*.py"]),
            ("cpp", ["git", "-C", str(ws), "grep", "-nIE",
                     r"^\s*#\s*include", "--",
                     "*.c", "*.cc", "*.cpp", "*.cxx", "*.h", "*.hpp", "*.hxx"]),
        ]
    else:
        tool = "python-re"
        cmds = []

    if cmds:
        for kind, cmd in cmds:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True,
                                      errors="replace", timeout=120)
            except (subprocess.TimeoutExpired, OSError):
                continue
            regex = _PY_IMPORT if kind == "py" else _CPP_INCLUDE
            for line in proc.stdout.splitlines():
                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue
                path, _, content = parts
                path = str(Path(path).resolve()).replace(str(ws) + "/", "") \
                    if path.startswith("/") else path
                m = regex.match(content) or regex.search(content)
                if m:
                    _record(kind, path, m.group(1))
    else:
        exts_py, exts_cpp = {".py"}, {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx"}
        count = 0
        for p in ws.rglob("*"):
            if count > 5000:
                break
            if not p.is_file():
                continue
            rel_parts = p.relative_to(ws).parts
            if any(part.startswith(".") for part in rel_parts):
                continue
            suffix = p.suffix.lower()
            if suffix not in exts_py and suffix not in exts_cpp:
                continue
            count += 1
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            rel = str(p.relative_to(ws))
            regex = _PY_IMPORT if suffix in exts_py else _CPP_INCLUDE
            kind = "py" if suffix in exts_py else "cpp"
            for m in regex.finditer(text):
                _record(kind, rel, m.group(1))

    return usage, tool


def _norm(name: str) -> str:
    return name.lower().replace("-", "_").split("[")[0]


def detect_deps(inp: DetectDepsInput) -> DetectDepsOutput:
    cached = _cache_get(inp.cache_prefix, inp.cache_mode)
    if cached is not None:
        cached["cache_hit"] = True
        return DetectDepsOutput.from_dict(cached)

    ws = Path(inp.workspace_abs)
    deps = (_parse_python_manifests(ws) + _parse_cpp_manifests(ws))[:_MAX_DEPS]
    usage, tool = _collect_imports(ws)

    declared_norm = {}
    for d in deps:
        declared_norm.setdefault(_norm(d["name"]), d)
        d["used_in"] = []

    for imp_name, files in usage.items():
        d = declared_norm.get(_norm(imp_name))
        if d is not None:
            d["used_in"] = sorted(set(d["used_in"] + files))[:_MAX_USED_IN]

    unresolved = [
        {"name": name, "files": sorted(files)[:5]}
        for name, files in sorted(usage.items())
        if _norm(name) not in declared_norm
    ][:_MAX_UNRESOLVED]

    doc = {
        "dependencies": deps,
        "unresolved_imports": unresolved,
        "grep_tool": tool,
        "cache_hit": False,
    }
    _cache_set(inp.cache_prefix, inp.cache_mode, doc)
    return DetectDepsOutput.from_dict(doc)

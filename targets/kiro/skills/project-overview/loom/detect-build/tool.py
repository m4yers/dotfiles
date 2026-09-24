"""Tool body for the `detect-build` task (loomv2 native contract).

Build half of the former project-detect. Resolution order:

1. Non-empty `build_system_override` -> verbatim, provenance
   "override:cli".
2. Manifest walk: pyproject.toml tool sections and build-system
   requires, setup.py/setup.cfg, lockfiles, tox.ini for Python;
   well-known top-level build manifests for C/C++.
3. Otherwise "unknown".

Then scans ~/.kiro/skills/**/SKILL.md for skills named
`<build_system>-*` and maps the family to a fallback build command.
Results cached via the `cache` skill under
`<cache_prefix>/detect-build`.
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Optional

import yaml

from io_types import DetectBuildInput, DetectBuildOutput

_CACHE_SH = (
    Path.home() / ".kiro" / "skills" / "home" / "cache" / "scripts" / "cache.sh"
)
_CACHE_NAME = "detect-build"

_BUILD_MATRIX: dict[str, str] = {
    "uv":         "uv build",
    "poetry":     "poetry build",
    "pdm":        "pdm build",
    "hatch":      "hatch build",
    "setuptools": "python -m build",
    "tox":        "tox",
    "make":       "make",
    "cmake":      "cmake -B build && cmake --build build",
    "autotools":  "./configure && make",
    "meson":      "meson setup build && meson compile -C build",
    "ninja":      "ninja",
    "scons":      "scons",
}

_PY_TOOL_TO_FAMILY = {"uv": "uv", "poetry": "poetry", "pdm": "pdm", "hatch": "hatch"}

_CPP_FILE_TO_FAMILY = [
    ("Makefile",       "make"),
    ("CMakeLists.txt", "cmake"),
    ("configure.ac",   "autotools"),
    ("meson.build",    "meson"),
    ("build.ninja",    "ninja"),
    ("SConstruct",     "scons"),
]

_KIRO_SKILLS_ROOT = Path.home() / ".kiro" / "skills"


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


def _detect_from_pyproject(pyproject: Path) -> Optional[tuple[str, str]]:
    try:
        with pyproject.open("rb") as fh:
            doc = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    tool = doc.get("tool", {})
    for name, family in _PY_TOOL_TO_FAMILY.items():
        if name in tool:
            return family, f"pyproject.toml:[tool.{name}]"
    requires = doc.get("build-system", {}).get("requires", [])
    if any("setuptools" in r for r in requires):
        return "setuptools", "pyproject.toml:[build-system].requires"
    return None


def detect(workspace: Path) -> tuple[str, str]:
    """Walk manifest markers in static-detection order."""
    pyproject = workspace / "pyproject.toml"
    if pyproject.is_file():
        hit = _detect_from_pyproject(pyproject)
        if hit is not None:
            return hit
    for name in ("setup.py", "setup.cfg"):
        if (workspace / name).is_file():
            return "setuptools", name
    if (workspace / "uv.lock").is_file():
        return "uv", "uv.lock"
    if (workspace / "poetry.lock").is_file():
        return "poetry", "poetry.lock"
    if (workspace / "tox.ini").is_file():
        return "tox", "tox.ini"
    for filename, family in _CPP_FILE_TO_FAMILY:
        if (workspace / filename).is_file():
            return family, filename
    return "unknown", "none"


def _read_frontmatter(skill_md: Path) -> Optional[dict[str, Any]]:
    try:
        text = skill_md.read_text()
    except OSError:
        return None
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    try:
        doc = yaml.safe_load(text[4:end])
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def scan_installed_skills(prefix: str) -> list[dict[str, Any]]:
    if prefix == "unknown":
        return []
    hits: list[dict[str, Any]] = []
    if not _KIRO_SKILLS_ROOT.is_dir():
        return hits
    for skill_md in _KIRO_SKILLS_ROOT.glob("**/SKILL.md"):
        fm = _read_frontmatter(skill_md)
        if fm is None:
            continue
        name = fm.get("name")
        if not isinstance(name, str) or not name.startswith(f"{prefix}-"):
            continue
        scripts_dir = skill_md.parent / "scripts"
        scripts = sorted(p.name for p in scripts_dir.iterdir()) if scripts_dir.is_dir() else []
        hits.append({
            "name": name,
            "path": str(skill_md.resolve()),
            "description": (fm.get("description") or "").strip(),
            "scripts": scripts,
        })
    hits.sort(key=lambda h: h["name"])
    return hits


def detect_build(inp: DetectBuildInput) -> DetectBuildOutput:
    cached = _cache_get(inp.cache_prefix, inp.cache_mode)
    if cached is not None and cached.get("override") == (inp.build_system_override or ""):
        cached.pop("override", None)
        cached["cache_hit"] = True
        return DetectBuildOutput.from_dict(cached)

    override = inp.build_system_override or ""
    if override:
        build_system, provenance = override, "override:cli"
    else:
        build_system, provenance = detect(Path(inp.workspace_abs))

    doc = {
        "build_system": build_system,
        "provenance": provenance,
        "installed_skills": scan_installed_skills(build_system),
        "fallback_build_cmd": _BUILD_MATRIX.get(build_system, ""),
        "cache_hit": False,
    }
    _cache_set(inp.cache_prefix, inp.cache_mode, {**doc, "override": override})
    return DetectBuildOutput.from_dict(doc)

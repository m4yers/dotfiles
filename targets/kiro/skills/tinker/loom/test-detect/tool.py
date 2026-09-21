"""Tool body for the `test-detect` task (loomv2 native contract).

Test half of the former project-detect. Resolution order:

1. Non-empty `test_system_override` -> verbatim, provenance
   "override:cli"; fresh `<override>-*` skill scan.
2. Otherwise the build-system family from build-detect, provenance
   "build-system"; build-detect's skill scan is reused as-is.

Maps the family to a fallback test command. Cached per
workspace+commit.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from io_types import TestDetectInput, TestDetectOutput

_CACHE_FILE = "test-detect.yaml"

_TEST_MATRIX: dict[str, str] = {
    "uv":         "uv run pytest",
    "poetry":     "poetry run pytest",
    "pdm":        "pdm run pytest",
    "hatch":      "hatch run pytest",
    "setuptools": "python -m pytest",
    "tox":        "tox -e py",
    "make":       "make test",
    "cmake":      "ctest --test-dir build",
    "autotools":  "make check",
    "meson":      "meson test -C build",
    "ninja":      "ninja test",
    "scons":      "scons test",
}

_KIRO_SKILLS_ROOT = Path.home() / ".kiro" / "skills"


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


def _scan_installed_skills(prefix: str) -> list[dict[str, Any]]:
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


def test_detect(inp: TestDetectInput) -> TestDetectOutput:
    override = inp.test_system_override or ""
    cached = _read_cache(inp.cache_dir, inp.cache_mode)
    if cached is not None and cached.get("override") == override \
            and cached.get("build_system_in") == inp.build_system:
        return TestDetectOutput(
            test_system=cached["test_system"],
            provenance=cached["provenance"],
            installed_skills=cached["installed_skills"],
            fallback_test_cmd=cached["fallback_test_cmd"],
            cache_hit=True,
        )

    if override:
        test_system = override
        provenance = "override:cli"
        installed_skills = _scan_installed_skills(test_system)
    elif inp.build_system and inp.build_system != "unknown":
        test_system = inp.build_system
        provenance = "build-system"
        installed_skills = inp.build_installed_skills or []
    else:
        test_system = "unknown"
        provenance = "none"
        installed_skills = []

    doc = {
        "test_system": test_system,
        "provenance": provenance,
        "installed_skills": installed_skills,
        "fallback_test_cmd": _TEST_MATRIX.get(test_system, ""),
        "cache_hit": False,
    }
    _write_cache(inp.cache_dir, inp.cache_mode,
                 {**doc, "override": override, "build_system_in": inp.build_system})
    return TestDetectOutput.from_dict(doc)

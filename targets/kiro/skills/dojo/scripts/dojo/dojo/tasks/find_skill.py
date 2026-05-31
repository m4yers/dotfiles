"""Tool task: discover skills under `~/.kiro/skills/`.

Two modes:
- No args: returns the full landscape — every namespace + every
  installed skill's `{name, namespace, path, type}`. Used by
  the update pipeline to populate `gather-update`'s picker.
- `--name N`: returns a single-entry `{name, namespace, path, type}`.
  Cascade-fails if not found or ambiguous. Used by the review
  pipeline.

Note: ~/.kiro/skills is a directory of symlinks (each
namespace symlinks into a dotfiles target). We walk with
`followlinks=True` so glob discovers SKILL.md files through
the symlink layer.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import typer

from loom import tool

from dojo.utils import emit, fail

ID = "find-skill"

SKILLS_ROOT = Path.home() / ".kiro" / "skills"

_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA       = _SKILL_ROOT / "schemas" / "find_skill.yaml"
SCHEMA_NAMED = _SKILL_ROOT / "schemas" / "find_skill_named.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"

# Directories holding installed Python deps and other noise —
# these may carry their own SKILL.md files (e.g. typer ships
# an .agents/skills tree).
_SKIP_DIR_PARTS = {".venv", "node_modules", "__pycache__",
                   "site-packages", ".git"}


def task(workdir: Path, *, depends_on_all=()):
    """Landscape mode tool task. Used by update."""
    return tool(
        ID,
        cmd=[str(SHIM), "find", "skill"],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def task_named(workdir: Path, name: str, *, depends_on_all=()):
    """Named mode tool task. Used by review."""
    return tool(
        ID,
        cmd=[str(SHIM), "find", "skill", "--name", name],
        output_schema=str(SCHEMA_NAMED),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def _extract_type(skill_md: Path) -> str:
    """Read `type:` from SKILL.md frontmatter; '' if missing."""
    if not skill_md.is_file():
        return ""
    in_fm = False
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_fm:
                in_fm = True
                continue
            break
        if in_fm and stripped.startswith("type:"):
            return stripped.split(":", 1)[1].strip()
    return ""


def _scan_landscape() -> dict:
    """Walk SKILLS_ROOT for SKILL.md files; return landscape."""
    if not SKILLS_ROOT.is_dir():
        return {"namespaces": [], "skills": []}

    skills: list[dict] = []
    namespaces: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(
            SKILLS_ROOT, followlinks=True):
        dirnames[:] = [d for d in dirnames
                       if d not in _SKIP_DIR_PARTS]
        if "SKILL.md" not in filenames:
            continue
        skill_dir = Path(dirpath)
        try:
            rel_parent = skill_dir.parent.relative_to(SKILLS_ROOT)
        except ValueError:
            continue
        if any(p in _SKIP_DIR_PARTS for p in rel_parent.parts):
            continue
        namespace = str(rel_parent) if rel_parent.parts else ""
        if namespace:
            namespaces.add(namespace)
        skills.append({
            "name": skill_dir.name,
            "namespace": namespace,
            "path": str(skill_dir),
            "type": _extract_type(skill_dir / "SKILL.md"),
        })

    skills.sort(key=lambda s: (s["namespace"], s["name"]))
    return {"namespaces": sorted(namespaces), "skills": skills}


def _resolve_named(name: str) -> dict:
    """Resolve a single skill by name; cascade-fail if 0/>1."""
    landscape = _scan_landscape()
    matches = [s for s in landscape["skills"] if s["name"] == name]
    if not matches:
        fail(f"skill '{name}' not found", name=name)
    if len(matches) > 1:
        listing = "\n".join(
            f"  {m['namespace']}/{m['name']} → {m['path']}"
            for m in matches
        )
        fail(f"skill '{name}' is ambiguous:\n{listing}",
             name=name, candidates=len(matches))
    return matches[0]


def cli_find(
    name: Optional[str] = typer.Option(
        None, "--name", "-n",
        help="If given, resolve a single skill by name and emit "
             "`{name, namespace, path, type}`. Otherwise emit the "
             "full landscape."),
) -> None:
    """`dojo.sh find skill [--name N]` — emit landscape or single skill."""
    if name is None:
        emit(_scan_landscape())
        return
    emit(_resolve_named(name))


# Back-compat alias for legacy imports.
def run() -> dict:
    return _scan_landscape()

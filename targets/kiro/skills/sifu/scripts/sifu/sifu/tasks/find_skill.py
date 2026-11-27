"""Tool task: discover skills under `~/.kiro/skills/`.

- `_scan_landscape()` returns `{namespaces: [str], skills: [{name,
  namespace, path, type}]}` for every installed skill.
- `_resolve_named(name)` returns one landscape entry plus
  `skill_dir` (== path) and `category` (first namespace component).
  Fails if the name is not found or ambiguous.
- `run(name)` returns `{skill_dir, name, category, type}`, the
  `loom/find-skill/io.yaml` output.

Note: ~/.kiro/skills is a directory of symlinks (each
namespace symlinks into a dotfiles target). We walk with
`followlinks=True` so glob discovers SKILL.md files through
the symlink layer.
"""
from __future__ import annotations

import os
from pathlib import Path

from sifu.autochecks._helpers import parse_frontmatter
from sifu.utils import SKILLS_ROOT, fail

# Directories holding installed Python deps and other noise —
# these may carry their own SKILL.md files (e.g. typer ships
# an .agents/skills tree).
_SKIP_DIR_PARTS = {".venv", "node_modules", "__pycache__",
                   "site-packages", ".git"}


def _extract_type(skill_md: Path) -> str:
    """Read `type:` from SKILL.md frontmatter; '' if missing."""
    if not skill_md.is_file():
        return ""
    fields, _ = parse_frontmatter(
        skill_md.read_text(encoding="utf-8").splitlines())
    return fields["type"][0] if "type" in fields else ""


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
    match = dict(matches[0])
    # Canonical locate-shape fields consumed by the audit core
    # and checks-report: skill_dir (== path) and category (the
    # first namespace component, e.g. 'home', 'aws').
    match["skill_dir"] = match["path"]
    namespace = match.get("namespace") or ""
    match["category"] = namespace.split("/", 1)[0] if namespace else "unknown"
    return match


def run(name: str) -> dict:
    """Resolve `name`; return `{skill_dir, name, category, type}`."""
    match = _resolve_named(name)
    return {"skill_dir": match["skill_dir"], "name": match["name"],
            "category": match["category"], "type": match["type"]}

"""Backing logic for `$LOOM graph new`. Idempotent.

Two modes:

- Absent ``<loom_root>/graph.yaml``: scaffold a starter by discovering
  task folders and pinning each to the current io.yaml version.
- Present ``<loom_root>/graph.yaml``: load, preserve every authored
  field (task entries, depends_on_all/any, when, latches, subgraph
  entries and their root paths, ordering, extra fields), and restamp
  each entry's ``version`` from the referenced task folder's current
  io.yaml. Subgraph entries restamp per the pinning logic in
  ``plan.to_graph_yaml`` / ``validate.versions.check_versions``.

Writes are atomic (temp + rename). Prints ``scaffolded ...``,
``repinned N task(s)``, or ``unchanged``.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from loom.discovery import load_graph_yaml, load_io_yaml
from loom.engine.store import atomic_write


# `to_graph_yaml` stamps subgraph entries with version=1 and
# `check_versions` skips them. Mirror that here.
_SUBGRAPH_VERSION = 1


def new_graph(loom_root: Path) -> Path:
    """Scaffold or refresh ``<loom_root>/graph.yaml``. Returns the path."""
    target = Path(loom_root) / "graph.yaml"
    if not target.exists():
        return _scaffold(Path(loom_root), target)
    return _refresh(Path(loom_root), target)


def _scaffold(loom_root: Path, target: Path) -> Path:
    """Discover task folders and write a fresh graph.yaml."""
    entries: list[dict] = []
    for folder in sorted(p for p in loom_root.iterdir() if p.is_dir()):
        if not (folder / "io.yaml").exists():
            continue
        entries.append({
            "id": folder.name,
            "kind": _guess_kind(folder),
            "version": load_io_yaml(folder).version,
        })
    atomic_write(target, yaml.safe_dump({"tasks": entries}, sort_keys=False))
    print(f"scaffolded {target} with {len(entries)} task(s)")
    return target


def _refresh(loom_root: Path, target: Path) -> Path:
    """Restamp version fields in an existing graph.yaml; preserve the rest."""
    parsed = load_graph_yaml(loom_root)
    expected = [_current_version(loom_root, entry) for entry in parsed["tasks"]]
    changes = sum(
        1 for entry, want in zip(parsed["tasks"], expected)
        if entry["version"] != want
    )
    if changes == 0:
        print("unchanged")
        return target
    new_text = _restamp_versions(target.read_text(), expected)
    atomic_write(target, new_text)
    print(f"repinned {changes} task(s)")
    return target


def _current_version(loom_root: Path, entry: dict) -> int:
    """Current pinned version for an entry, mirroring `to_graph_yaml`."""
    if entry["kind"] == "subgraph":
        return _SUBGRAPH_VERSION
    return load_io_yaml(loom_root / entry["id"]).version


def _restamp_versions(raw: str, expected: list[int]) -> str:
    """Replace `version: N` occurrences in order, skipping fully-comment lines.

    Task entries appear in the same order in the parsed doc and the raw
    text (schema-validated). Latch entries carry no ``version`` field.
    """
    it = iter(expected)
    pattern = re.compile(r"(\bversion:\s*)\d+")

    def repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{next(it)}"

    out: list[str] = []
    for line in raw.splitlines(keepends=True):
        if re.match(r"^\s*#", line):
            out.append(line)
            continue
        out.append(pattern.sub(repl, line))
    return "".join(out)


def _guess_kind(folder: Path) -> str:
    """Inspect the folder for a body file to guess kind. Default: tool."""
    if (folder / "tool.py").exists() or (folder / "tool.sh").exists():
        return "tool"
    if (folder / "prompt.md.j2").exists():
        return "agent"
    if (folder / "message.md.j2").exists():
        return "human"
    return "tool"

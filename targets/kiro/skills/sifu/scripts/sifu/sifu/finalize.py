"""`sifu.sh loom-finalize <skill_dir>` — finish a loomv2 scaffold.

One command for the post-write sequence both skill-materialize and
modify-changes need: regenerate ``io_types.py`` for every ``tool.py``
task, make every ``tool.sh`` executable, re-pin each ``graph*.yaml``
entry's ``version`` to its folder's current ``io.yaml`` version, and
validate every graph. Exits non-zero on the first failure.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

from sifu.utils import SKILLS_ROOT, emit, fail

LOOM_SH = SKILLS_ROOT / "home" / "loomv2" / "scripts" / "loom.sh"

# `- id: X` ... `version: N` within one graph entry; `ref:` names the
# backing folder when it differs from the id.
_ENTRY_RE = re.compile(
    r"(?P<head>^- id: (?P<id>[a-z][a-z0-9-]*)\n(?:  (?!- id:).*\n)*?"
    r"  version: )(?P<ver>\d+)", re.MULTILINE)
_REF_RE = re.compile(r"^  ref: ([a-z][a-z0-9-]*)$", re.MULTILINE)
_KIND_RE = re.compile(r"^  kind: (\w+)$", re.MULTILINE)


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _io_version(folder: Path) -> int | None:
    io = folder / "io.yaml"
    if not io.is_file():
        return None
    doc = yaml.safe_load(io.read_text(encoding="utf-8")) or {}
    return int(doc.get("version", 1))


def _repin(graph: Path, root: Path) -> list[str]:
    """Set each tool/agent/human entry's version to its folder's io
    version. Returns the ids changed."""
    text = graph.read_text(encoding="utf-8")
    changed: list[str] = []

    def repl(m: re.Match) -> str:
        block_end = text.find("\n- id:", m.start() + 1)
        block = text[m.start():block_end if block_end != -1 else len(text)]
        kind = _KIND_RE.search(block)
        if kind and kind.group(1) == "subgraph":
            return m.group(0)
        ref = _REF_RE.search(block)
        folder = root / (ref.group(1) if ref else m.group("id"))
        current = _io_version(folder)
        if current is None or current == int(m.group("ver")):
            return m.group(0)
        changed.append(m.group("id"))
        return f"{m.group('head')}{current}"

    new = _ENTRY_RE.sub(repl, text)
    if new != text:
        graph.write_text(new, encoding="utf-8")
    return changed


def run(skill_dir: Path) -> dict:
    roots = sorted(p for p in skill_dir.glob("loom*") if p.is_dir())
    if not roots:
        fail(f"no loom*/ root under {skill_dir}")
    report = {"io_python": [], "chmod": [], "repinned": {}, "validated": []}
    for root in roots:
        for tool_py in sorted(root.glob("*/tool.py")):
            res = _run([str(LOOM_SH), "task", "io-python", tool_py.parent.name,
                        "--loom-root", str(root)])
            if res.returncode != 0:
                fail(f"io-python failed for {tool_py.parent}",
                     stderr=res.stderr.strip()[-800:])
            report["io_python"].append(str(tool_py.parent))
        for tool_sh in sorted(root.glob("*/tool.sh")):
            mode = tool_sh.stat().st_mode
            if not mode & 0o111:
                tool_sh.chmod(mode | 0o755)
                report["chmod"].append(str(tool_sh))
        for graph in sorted(root.glob("graph*.yaml")):
            changed = _repin(graph, root)
            if changed:
                report["repinned"][str(graph)] = changed
    for root in roots:
        for graph in sorted(root.glob("graph*.yaml")):
            res = _run([str(LOOM_SH), "validate", str(skill_dir),
                        "--graph", str(graph)])
            if res.returncode != 0:
                fail(f"validate failed for {graph}",
                     stderr=(res.stderr or res.stdout).strip()[-800:])
            report["validated"].append(str(graph))
    return report


def cli_loom_finalize(skill_dir: Path) -> None:
    """io-python every tool.py, chmod +x every tool.sh, re-pin and validate
    every graph*.yaml under the skill's loom*/ roots."""
    emit(run(skill_dir.expanduser().resolve()))


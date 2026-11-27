"""Tool task: render the `design` agent's YAML output as a
human-readable markdown report.

The `design` agent emits a structured YAML at
`tasks/NN-design/output.yaml`. That YAML interleaves
multiline literal blocks for `sections[].outline`,
`files[].content_outline`, and `rationale`, which makes it
hard to scan during the `design-review` human gate. This
tool reads the YAML and writes a markdown rendering to
`<task_workdir>/design.md` so the gate can show prose to
the user instead of YAML.

The rendered file is read-only presentation. The canonical
edit target remains the upstream design YAML — edits round-
trip back to YAML and are copied into the design-review
output by the gate.
"""
from __future__ import annotations

from pathlib import Path

import yaml


from sifu.utils import emit, fail


_SKILL_ROOT = Path(__file__).resolve().parents[4]


def _render(design: dict) -> str:
    """Render the design YAML payload as a high-level markdown
    overview. Layout depends on `frontmatter.type`:

    - For workflow skills: folder tree, CLI surface, per-task
      sections (each task gets its own section so descriptions
      have room), and rationale. The `sections` field is rendered
      only when present, since the workflow skill template
      already standardises SKILL.md structure.
    - For all other skill types: folder tree, sections, files,
      tasks (table — usually empty), rationale.

    Skips deeply detailed `content_outline` blocks — those live
    in the YAML and feed materialize.
    """
    lines: list[str] = []

    fm = design.get("frontmatter") or {}
    name = fm.get("name", "<unnamed>")
    skill_type = fm.get("type", "<no-type>")
    description = (fm.get("description") or "").strip()
    is_workflow = skill_type == "workflow"

    lines.append(f"# Design: `{name}` ({skill_type})")
    lines.append("")
    if description:
        lines.append("> " + description.replace("\n", "\n> "))
        lines.append("")

    # Folder tree of all files (paths from design.files[]).
    files = design.get("files") or []
    paths = sorted(str((f.get("path") or "").strip())
                   for f in files
                   if (f.get("path") or "").strip())
    lines.append("## Folder structure")
    lines.append("")
    lines.append("```")
    lines.extend(_render_tree(name, paths))
    lines.append("```")
    lines.append("")

    # CLI surface — workflow-type skills typically declare one;
    # also rendered for non-workflow types when present. Rendered
    # as a wrapping bullet list (not a table) so it reflows to the
    # mdformat wrap width instead of forcing a wide aligned table.
    cli = design.get("cli_surface") or []
    if cli:
        lines.append("## CLI surface")
        lines.append("")
        for entry in cli:
            cmd = (entry.get("command") or "").strip()
            args = (entry.get("args") or "").strip()
            desc = _first_paragraph((entry.get("description") or "").strip())
            head = f"`{cmd}`"
            if args:
                head += f" `{args}`"
            lines.append(f"- {head} — {desc}")
        lines.append("")

    # Sections — for workflow skills, render only when explicitly
    # populated (otherwise the workflow.md.j2 template handles
    # the SKILL.md structure). For other types, always render.
    sections = design.get("sections") or []
    if sections or not is_workflow:
        lines.append("## SKILL.md sections")
        lines.append("")
        if not sections:
            if is_workflow:
                lines.append(
                    "_(empty — the workflow skill template "
                    "supplies the standard sections)_")
            else:
                lines.append("_(none — design declared no sections)_")
            lines.append("")
        for i, s in enumerate(sections, start=1):
            heading = (s.get("heading") or "").strip()
            outline = _first_paragraph((s.get("outline") or "").strip())
            lines.append(f"{i}. **{heading}** — {outline}")
        if sections:
            lines.append("")

    # Tasks — one compact entry per task for every skill type,
    # rendered as a wrapping bullet list (not a table) for the same
    # mdformat reason as the CLI surface above. Consecutive tasks
    # sharing a `ref` (instances of one task folder) collapse into
    # a single entry so a 32-way fan-out reads as one line.
    tasks = design.get("tasks") or []
    if tasks:
        heading = "## Tasks" if is_workflow else "## Tasks (loom DAG)"
        lines.append(heading)
        lines.append("")
        for group in _group_by_ref(tasks):
            first = group[0]
            head = f"`{(first.get('id') or '').strip()}`"
            if len(group) > 1:
                last = (group[-1].get("id") or "").strip()
                ref = (first.get("ref") or "").strip()
                head += f"..`{last}` (x{len(group)}, ref `{ref}`)"
            kind = (first.get("kind") or "").strip()
            deps = ", ".join(d for d in (first.get("depends_on") or [])
                             if d)
            deps_part = f" · deps: {deps}" if deps else ""
            desc = _first_paragraph(
                (first.get("description") or "").strip())
            lines.append(f"- {head} ({kind}){deps_part} — {desc}")
        lines.append("")

    # Per-file overview: path + 1-line purpose only.
    lines.append("## Files (purpose)")
    lines.append("")
    if not files:
        lines.append("_(SKILL.md only)_")
        lines.append("")
    for f in files:
        path = (f.get("path") or "").strip()
        purpose = _first_paragraph((f.get("purpose") or "").strip())
        lines.append(f"- `{path}` — {purpose}")
    if files:
        lines.append("")

    # Rationale.
    rationale = (design.get("rationale") or "").strip()
    if rationale:
        lines.append("## Rationale")
        lines.append("")
        lines.append(rationale)
        lines.append("")

    # Pointer to the canonical YAML for anyone wanting per-file
    # content_outline detail (used by materialize).
    lines.append("---")
    lines.append("")
    lines.append(
        "Detailed per-file `content_outline` lives in the raw "
        "design YAML alongside this file (used by materialize).")
    lines.append("")

    return "\n".join(lines)


def _group_by_ref(tasks: list[dict]) -> list[list[dict]]:
    """Group consecutive tasks that share a non-empty `ref` (instances
    of one task folder). Tasks without `ref` form singleton groups."""
    groups: list[list[dict]] = []
    for t in tasks:
        ref = (t.get("ref") or "").strip()
        if (groups and ref
                and (groups[-1][0].get("ref") or "").strip() == ref):
            groups[-1].append(t)
        else:
            groups.append([t])
    return groups


def _first_paragraph(text: str) -> str:
    """Collapse a multi-line outline to a single scannable
    line: take the first paragraph (up to the first blank
    line) and join its lines with single spaces."""
    if not text:
        return ""
    para = text.split("\n\n", 1)[0]
    return " ".join(line.strip() for line in para.splitlines()
                    if line.strip())


def _render_tree(root_name: str, paths: list[str]) -> list[str]:
    """Render `paths` as a UTF-8 box-drawing directory tree
    rooted at `root_name`. Paths are slash-separated relative
    to root. Directories are inferred from path components and
    are listed before files at each level. SKILL.md is always
    inserted at the root level so the tree shows the canonical
    layout.
    """
    # Build a nested dict where directories map to dicts and
    # files map to None (a leaf marker).
    tree: dict = {"SKILL.md": None}
    for p in paths:
        parts = [seg for seg in p.split("/") if seg]
        node = tree
        for seg in parts[:-1]:
            child = node.get(seg)
            if not isinstance(child, dict):
                # Either not present, or a same-named file
                # collision (shouldn't happen with valid
                # paths). Replace with a directory.
                child = {}
                node[seg] = child
            node = child
        if parts:
            # Don't overwrite an existing directory of the same
            # name with a file marker.
            leaf_name = parts[-1]
            if leaf_name not in node:
                node[leaf_name] = None

    lines: list[str] = [f"{root_name}/"]
    _walk_tree(tree, prefix="", out=lines)
    return lines


def _walk_tree(node: dict, prefix: str, out: list[str]) -> None:
    """Recursive helper for `_render_tree`. Emits one line per
    entry with proper ├── / └── / │ box characters. Directories
    sort before files at each level for a conventional view.
    """
    def is_dir(name: str) -> bool:
        return isinstance(node[name], dict)

    # Dirs first (alphabetical), then files (alphabetical).
    keys = sorted(node.keys(), key=lambda k: (not is_dir(k), k))
    for i, key in enumerate(keys):
        last = i == len(keys) - 1
        connector = "└── " if last else "├── "
        suffix = "/" if is_dir(key) else ""
        out.append(f"{prefix}{connector}{key}{suffix}")
        if is_dir(key):
            extension = "    " if last else "│   "
            _walk_tree(node[key], prefix + extension, out)



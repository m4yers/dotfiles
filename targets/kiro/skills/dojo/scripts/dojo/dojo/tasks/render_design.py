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
from typing import Optional
import os

import typer
import yaml

from loom import tool

from dojo.utils import emit, fail

ID = "design-render"

_SKILL_ROOT = Path(__file__).resolve().parents[4]
SCHEMA = _SKILL_ROOT / "schemas" / "design_render.yaml"
SHIM = _SKILL_ROOT / "scripts" / "dojo.sh"


def task(*, depends_on_all=()):
    return tool(
        ID,
        cmd=[
            str(SHIM), "pipeline", "render-design",
            "--design", "${task_path:design-author}",
        ],
        output_schema=str(SCHEMA),
        depends_on_all=list(depends_on_all) if depends_on_all else None,
    )


def _render(design: dict) -> str:
    """Render the design YAML payload as a high-level markdown
    overview. Layout depends on `frontmatter.type`:

    - For workflow skills: folder tree, CLI surface, per-task
      sections (each task gets its own section so descriptions
      have room), a loom-visualise diagram synthesised from
      `tasks`, and rationale. The `sections` field is rendered
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

    # Tasks — workflow skills get one section per task with the
    # full description (descriptions can be 3-5 sentences for
    # keystone tasks and warrant more space than a table cell).
    # Other types render a compact table when tasks are present.
    tasks = design.get("tasks") or []
    if tasks:
        if is_workflow:
            lines.append("## Tasks")
            lines.append("")
            for i, t in enumerate(tasks, start=1):
                tid = (t.get("id") or "").strip()
                kind = (t.get("kind") or "").strip()
                deps = ", ".join(d for d in (t.get("depends_on") or [])
                                 if d) or "—"
                desc = (t.get("description") or "").strip()
                lines.append(
                    f"### {i}. `{tid}` ({kind})  ·  deps: {deps}")
                lines.append("")
                lines.append(desc)
                lines.append("")
            # Synthesise a loom-visualise diagram from tasks[].
            diagram = _visualise_tasks(name, tasks)
            if diagram:
                lines.append("## Plan visualisation")
                lines.append("")
                lines.append("```")
                lines.append(diagram.rstrip())
                lines.append("```")
                lines.append("")
        else:
            lines.append("## Tasks (loom DAG)")
            lines.append("")
            lines.append("| # | id | kind | depends on | description |")
            lines.append("|---|---|---|---|---|")
            for i, t in enumerate(tasks, start=1):
                tid = (t.get("id") or "").strip()
                kind = (t.get("kind") or "").strip()
                deps = ", ".join(d for d in (t.get("depends_on") or [])
                                 if d) or "—"
                desc = _first_paragraph((t.get("description") or "").strip())
                lines.append(f"| {i} | `{tid}` | {kind} | {deps} | {desc} |")
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


def _visualise_tasks(plan_name: str, tasks: list[dict]) -> str:
    """Synthesise a loom-visualise ASCII diagram from a design's
    tasks[] array. Builds an in-memory LoomPlan and calls loom's
    visualise API. Returns "" on any failure (visualisation is a
    best-effort presentation aid; failure should not block the
    rendered design)."""
    try:
        from loom.engine.models import LoomPlan
        from loom.visualise import visualise
        plan_dict = {
            "tasks": [
                {
                    "id":             (t.get("id") or "").strip(),
                    "kind":           (t.get("kind") or "agent").strip(),
                    "depends_on_all": list(t.get("depends_on") or []),
                    "status":         "pending",
                    **({"when": t["when"]} if t.get("when") else {}),
                    **({"latch": t["latch"]} if t.get("latch") else {}),
                }
                for t in tasks
                if (t.get("id") or "").strip()
            ],
        }
        if not plan_dict["tasks"]:
            return ""
        loom_plan = LoomPlan.from_dict(plan_dict)
        return visualise(
            loom_plan,
            show_when=True,
            ascii_only=False,
            workdir_basename=plan_name,
        )
    except Exception:
        # Visualisation is best-effort; fall back to no diagram.
        return ""


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


def cli_render(
    design: Path = typer.Option(
        ..., "--design",
        help="Path to the design agent's output.yaml"),
    out: Optional[Path] = typer.Option(
        None, "--out",
        help="Override output path (defaults to "
             "$TASK_WORKDIR/design.md)"),
) -> None:
    """`dojo.sh pipeline render-design ...` — emit `{ok, report_path}`."""
    if not design.exists():
        fail(f"design output not found at {design}")
    payload = yaml.safe_load(design.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        fail(f"design output at {design} is not a YAML mapping")

    if out is None:
        # Loom sets TASK_WORKDIR for tool tasks. Default the
        # rendered markdown to <task_workdir>/design.md so the
        # design-review gate can find it via report_path.
        td_env = os.environ.get("TASK_WORKDIR")
        if not td_env:
            fail(
                "TASK_WORKDIR env var missing; pass --out explicitly "
                "when running outside a loom task")
        out = Path(td_env) / "design.md"

    out.parent.mkdir(parents=True, exist_ok=True)
    import mdformat
    rendered = mdformat.text(_render(payload), options={"wrap": 80})
    out.write_text(rendered, encoding="utf-8")

    emit({"ok": True, "report_path": str(out.resolve())})

"""Report rendering — composed.yaml → final report markdown.

Single CLI command (``render``) used by the ``render_report`` tool
task. Reads ``<workdir>/composed.yaml``, flattens it for the report
template, invokes the shared renderer at
``$SKILLS/home/template/scripts/render.sh``, post-processes with
mdformat, and emits the rendered report plus a result envelope.

Alongside the report, writes one fully-rendered synthesis artifact
per proposed synthesis page into ``<workdir>/synthesis/<slug>.md``
so the gate reviewer can preview the eventual vault file shape and
the materialize step has ready-to-write content.

Templates render through the shared renderer instead of a per-skill
jinja Environment so curator does not vendor jinja2 (per
conventions.md § Template Rendering).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Annotated

import typer
import yaml
from slugify import slugify

from curator.utils import emit, fail


app = typer.Typer(
    help="Report rendering.",
    no_args_is_help=True,
)

_SKILL_ROOT      = Path(__file__).resolve().parent.parent.parent
_TEMPLATES_DIR   = _SKILL_ROOT / "templates"
_REPORT_TEMPLATE = _TEMPLATES_DIR / "report.md.j2"
_RENDER_SH       = (Path(os.environ.get("SKILLS",
                                          str(Path.home() / ".kiro/skills"))).
                    joinpath("home/template/scripts/render.sh"))

_FLAT_BUCKETS = ("keywords", "people", "models", "synthesis",
                  "related_sources")


def _flatten(composed: dict) -> dict:
    """Translate composer output into report-template variables.

    Handles both the flat layout the composer agent emits and the
    legacy nested ``proposals.*`` layout."""
    proposals = composed.get("proposals", {}) or {}
    def _list(name):
        return list(composed.get(name) or proposals.get(name) or [])
    flat = {
        "summary":         composed.get("summary", ""),
        "keywords":        _list("keywords"),
        "people":          _list("people"),
        "models":          _list("models"),
        "topics":          _list("topics"),
        "synthesis":       _list("synthesis_pages") or _list("synthesis"),
        "related_sources": _list("related_sources"),
        "failed_kinds":    list(composed.get("failed_kinds") or []),
        "issues":          list(composed.get("issues") or []),
        "quintet":         composed.get("quintet", {}),
        "topic":           composed.get("topic", ""),
    }
    # Surface judge-flagged issues to the template as _judge_issues
    # so it can render them inline as ⚠ sub-bullets.
    for bucket in _FLAT_BUCKETS:
        for item in flat[bucket]:
            if isinstance(item, dict) and item.get("issues"):
                item["_judge_issues"] = item["issues"]
    return flat


def _render_report(variables: dict) -> str:
    """Invoke the shared renderer with ``--trim-blocks/--lstrip-blocks``
    enabled (the report template is whitespace-sensitive). Returns
    the rendered text. Raises CalledProcessError on renderer failure
    so the caller can surface stderr.

    ``VIRTUAL_ENV`` is stripped from the subprocess env so the
    renderer's ``uv run`` resolves to its own venv (curator runs
    under its own VIRTUAL_ENV which would otherwise conflict)."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8",
    ) as f:
        json.dump(variables, f)
        vars_file = f.name

    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    try:
        proc = subprocess.run(
            [
                str(_RENDER_SH),
                "--template",       str(_REPORT_TEMPLATE),
                "--include-dir",    str(_TEMPLATES_DIR),
                "--trim-blocks",
                "--lstrip-blocks",
                "--json-vars",      vars_file,
            ],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
    finally:
        Path(vars_file).unlink(missing_ok=True)
    return proc.stdout


def _write_synthesis_artifacts(
    wd: Path,
    synthesis_pages: list[dict],
) -> list[str]:
    """Write each synthesis page's ``body`` to ``<wd>/synthesis/<slug>.md``.

    Slug is derived from the page's title via ``python-slugify``.
    Returns the list of absolute paths written. Pages without a
    ``body`` field are skipped (the schema requires it for new runs,
    but legacy compose outputs may be missing it).

    The synthesis subdir is wiped fresh on each render so stale
    artifacts from an aborted compose do not linger.
    """
    out_dir = wd / "synthesis"
    if out_dir.exists():
        for old in out_dir.iterdir():
            if old.is_file():
                old.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for page in synthesis_pages:
        body = page.get("body")
        title = page.get("title")
        if not body or not title:
            continue
        slug = slugify(title, max_length=80) or "synthesis"
        path = out_dir / f"{slug}.md"
        # Format the body for consistent wrapping, same as the report.
        import mdformat
        formatted = mdformat.text(body, options={"wrap": 80},
                                    extensions={"gfm"})
        path.write_text(formatted, encoding="utf-8")
        written.append(str(path))
    return written


@app.command("render")
def cli_render(
    workdir: Annotated[str, typer.Argument(
        help="Run workdir; reads <wd>/composed.yaml, writes "
             "<wd>/tasks/render_report/output.yaml + report.md "
             "+ synthesis/<slug>.md per synthesis page.")],
) -> None:
    """Render the final report markdown from composed.yaml."""
    wd = Path(workdir).resolve()
    from engine import store
    plan = store.load_plan(wd)
    composed_path = store.task_output_path(wd, "compose", plan=plan)
    if not composed_path.exists():
        fail(f"composed.yaml missing at {composed_path}")

    composed = yaml.safe_load(composed_path.read_text(encoding="utf-8"))
    if not isinstance(composed, dict):
        fail(f"composed.yaml is not a mapping (got {type(composed).__name__})")

    vars_ = _flatten(composed)

    try:
        rendered = _render_report(vars_)
    except subprocess.CalledProcessError as e:
        fail(f"render failed: {e.stderr.strip() or e}")

    # Format with mdformat (--wrap 80) for consistent line wrapping
    # before writing. mdformat is a curator dep — imported directly.
    import mdformat
    formatted = mdformat.text(rendered, options={"wrap": 80}, extensions={"gfm"})

    report_path = wd / "report.md"
    report_path.write_text(formatted, encoding="utf-8")

    synthesis_paths = _write_synthesis_artifacts(wd, vars_.get("synthesis") or [])

    emit({
        "ok":               True,
        "report_path":      str(report_path),
        "synthesis_paths":  synthesis_paths,
        "buckets":          {k: len(vars_.get(k, [])) for k in _FLAT_BUCKETS},
    })

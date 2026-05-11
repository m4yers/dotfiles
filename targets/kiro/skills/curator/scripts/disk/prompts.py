"""Render every extractor and judge prompt for a workdir.

Deterministic drivers. The orchestrator calls these once per wave
and then only has to dispatch ``subagent`` for each rendered prompt.

All five extractor kinds share a single sub-agent role
(``curator-extractor``); specialization comes from the rendered
prompt at ``<wd>/prompts/<kind>.md``. Judges share ``curator-judge``.

Agents do not write JSON output files. They call per-item builders
on ``disk.sh`` (e.g. ``item-add --kind keyword ...``) which assemble
and schema-validate the canonical files. The rendered prompt
contains concrete CLI examples for the agent's specific kind; those
CLI examples live in the jinja templates, not in this module.

Output of each render call:
  {workdir}/prompts/<kind>.md    — rendered prompt, one per kind
  stdout JSON: {prompts: {kind: path}, workdir, ok: True}
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from vault import context

# Project roots derived from this file's location so the module works
# regardless of the caller's CWD.
# __file__ = <skills>/home/curator/scripts/disk/prompts.py
CURATOR_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_ROOT = CURATOR_ROOT.parent.parent
TEMPLATE_SKILL_ROOT = SKILLS_ROOT / "home" / "template"
# Every jinja template lives alongside the disk tool's Python package
# (moved from <curator>/templates/ so the disk tool owns its own
# renderer inputs).
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# Per-extractor metadata.
#
# ``canonical_file``   — canonical JSON file the extractor's builders write.
# ``schema_name``      — matching JSON Schema under
#                        ``scripts/disk/schemas/``.
# ``context_key``      — slice of `context.build_context()` the extractor
#                        consults for dedup; None = no vault dedup.
# ``anatomy_template`` — filename under ``templates/`` rendered via
#                        render.sh into the page_anatomy prompt variable;
#                        None = no page anatomy (JSON-only extractor).
EXTRACTORS = [
    ("summary",  "summary.json",  "summary.schema.json",  None,       None),
    ("sources",  "sources.json",  "sources.schema.json",  None,       None),
    ("keywords", "keywords.json", "items.schema.json",    "keywords", "page-anatomy-keyword.j2"),
    ("people",   "people.json",   "items.schema.json",    "people",   "page-anatomy-person.j2"),
    ("models",   "models.json",   "items.schema.json",    "models",   "page-anatomy-model.j2"),
]


def render_all(
    workdir: str | Path,
    source_vault_path: str,
    content_type: str = "unknown",
    topic: str = "",
) -> dict:
    """Render all 5 extractor prompts and return a {kind: path} map."""
    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise FileNotFoundError(f"workdir not found: {wd}")
    source_md = wd / "source.md"
    if not source_md.exists():
        raise FileNotFoundError(f"source.md missing: {source_md}")

    ctx = context.build_context()

    prompts_dir = wd / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (wd / "bodies").mkdir(exist_ok=True)

    template_path = TEMPLATES_DIR / "extractor-prompt.j2"
    render_sh = TEMPLATE_SKILL_ROOT / "scripts" / "render.sh"

    prompts: dict[str, str] = {}
    for kind, _out_name, schema_name, ctx_key, anatomy_template in EXTRACTORS:
        if ctx_key is not None:
            existing = [
                {"name": r["name"], "aliases": r["aliases"]}
                for r in ctx[ctx_key]
            ]
            anatomy = _render_anatomy(anatomy_template)
        else:
            existing = []
            anatomy = (
                f"No vault-page anatomy for this extractor. "
                f"Output shape is fully described by {schema_name}."
            )

        cmd = [
            str(render_sh),
            "--template", str(template_path),
            "--var", f"kind={kind}",
            "--var", f"source_md_path={source_md}",
            "--var", f"source_vault_path={source_vault_path}",
            "--var", f"existing_names={json.dumps(existing, ensure_ascii=False)}",
            "--var", f"page_anatomy={anatomy}",
            "--var", f"workdir={wd}",
            "--var", f"skills_root={SKILLS_ROOT}",
            "--var", f"content_type={content_type}",
            "--var", f"topic={topic}",
            "--var", "prior_issues=",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"render failed for {kind}: {result.stderr.strip()}"
            )
        prompt_path = prompts_dir / f"{kind}.md"
        prompt_path.write_text(result.stdout, encoding="utf-8")
        prompts[kind] = str(prompt_path)

    return {"prompts": prompts, "workdir": str(wd), "ok": True}


def render_retry_one(
    workdir: str | Path,
    kind: str,
    source_vault_path: str,
    prior_attempt: int,
    content_type: str = "unknown",
    topic: str = "",
) -> dict:
    """Re-render one extractor prompt with judge REJECT issues appended.

    Reads ``<wd>/verdicts/<kind>-attempt-<N>.json`` where N = prior_attempt,
    extracts every REJECT verdict's id and issues, formats them as markdown,
    and renders the standard extractor prompt with that text bound to the
    ``prior_issues`` template variable. Overwrites ``<wd>/prompts/<kind>.md``.

    Raises ``FileNotFoundError`` if the per-attempt verdict file is missing or
    ``ValueError`` if it contains no REJECT items (nothing to retry on).
    """
    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise FileNotFoundError(f"workdir not found: {wd}")

    valid_kinds = {row[0] for row in EXTRACTORS}
    if kind not in valid_kinds:
        raise ValueError(
            f"kind must be one of {sorted(valid_kinds)}, got {kind!r}"
        )

    verdict_path = wd / "verdicts" / f"{kind}-attempt-{prior_attempt}.json"
    if not verdict_path.is_file():
        raise FileNotFoundError(f"verdict file not found: {verdict_path}")

    verdict_data = json.loads(verdict_path.read_text(encoding="utf-8"))
    rejects = [
        v for v in verdict_data.get("verdicts", [])
        if v.get("verdict") == "REJECT"
    ]
    if not rejects:
        raise ValueError(
            f"no REJECT verdicts in {verdict_path}; nothing to retry"
        )

    prior_issues = _format_reject_issues(rejects)

    # Look up the extractor's metadata to render its prompt.
    _, _, schema_name, ctx_key, anatomy_template = next(
        row for row in EXTRACTORS if row[0] == kind
    )
    ctx = context.build_context()

    if ctx_key is not None:
        existing = [
            {"name": r["name"], "aliases": r["aliases"]}
            for r in ctx[ctx_key]
        ]
        anatomy = _render_anatomy(anatomy_template)
    else:
        existing = []
        anatomy = (
            f"No vault-page anatomy for this extractor. "
            f"Output shape is fully described by {schema_name}."
        )

    source_md = wd / "source.md"
    if not source_md.exists():
        raise FileNotFoundError(f"source.md missing: {source_md}")

    template_path = TEMPLATES_DIR / "extractor-prompt.j2"
    render_sh = TEMPLATE_SKILL_ROOT / "scripts" / "render.sh"

    cmd = [
        str(render_sh),
        "--template", str(template_path),
        "--var", f"kind={kind}",
        "--var", f"source_md_path={source_md}",
        "--var", f"source_vault_path={source_vault_path}",
        "--var", f"existing_names={json.dumps(existing, ensure_ascii=False)}",
        "--var", f"page_anatomy={anatomy}",
        "--var", f"workdir={wd}",
        "--var", f"skills_root={SKILLS_ROOT}",
        "--var", f"content_type={content_type}",
        "--var", f"topic={topic}",
        "--var", f"prior_issues={prior_issues}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"render failed for retry of {kind}: {result.stderr.strip()}"
        )
    prompts_dir = wd / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    prompt_path = prompts_dir / f"{kind}.md"
    prompt_path.write_text(result.stdout, encoding="utf-8")
    return {
        "prompt": str(prompt_path),
        "kind": kind,
        "prior_attempt": prior_attempt,
        "reject_count": len(rejects),
        "ok": True,
    }


def _format_reject_issues(rejects: list[dict]) -> str:
    """Format REJECT verdicts as markdown for the retry prompt."""
    lines: list[str] = []
    for v in rejects:
        lines.append(f"### {v['id']}")
        for issue in v.get("issues", []):
            sev = issue.get("severity", "?")
            cat = issue.get("category", "?")
            msg = issue.get("message", "").strip()
            loc = issue.get("location")
            evidence = issue.get("source_evidence")
            head = f"- **[{sev}/{cat}]** {msg}"
            if loc:
                head += f" _(at {loc})_"
            lines.append(head)
            if evidence:
                lines.append(f"  - source evidence: {evidence.strip()}")
        if v.get("rewrite_suggestion"):
            lines.append(
                f"- judge rewrite suggestion: "
                f"{v['rewrite_suggestion'].strip()}"
            )
        lines.append("")
    return "\n".join(lines).rstrip()


def render_all_judges(
    workdir: str | Path,
    source_vault_path: str,
    attempt: int = 1,
    content_type: str = "unknown",
    topic: str = "",
) -> dict:
    """Render all 5 judge prompts (one curator-judge dispatch each)."""
    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise FileNotFoundError(f"workdir not found: {wd}")
    source_md = wd / "source.md"
    if not source_md.exists():
        raise FileNotFoundError(f"source.md missing: {source_md}")
    # Attempt must be within the shared retry budget (see SKILL.md Rule 6).
    if attempt < 1 or attempt > 3:
        raise ValueError(f"attempt must be 1..3, got {attempt}")

    ctx = context.build_context()

    prompts_dir = wd / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (wd / "verdicts").mkdir(exist_ok=True)

    template_path = TEMPLATES_DIR / "judge-prompt.j2"
    render_sh = TEMPLATE_SKILL_ROOT / "scripts" / "render.sh"

    prompts: dict[str, str] = {}
    for kind, out_name, schema_name, ctx_key, anatomy_template in EXTRACTORS:
        if ctx_key is not None:
            existing = [
                {"name": r["name"], "aliases": r["aliases"]}
                for r in ctx[ctx_key]
            ]
            anatomy = _render_anatomy(anatomy_template)
        else:
            existing = []
            anatomy = (
                f"No vault-page anatomy for this extractor. "
                f"Output shape is fully described by {schema_name}."
            )

        extractor_output = wd / out_name

        cmd = [
            str(render_sh),
            "--template", str(template_path),
            "--var", f"kind={kind}",
            "--var", f"source_md_path={source_md}",
            "--var", f"extractor_output_path={extractor_output}",
            "--var", f"attempt={attempt}",
            "--var", f"existing_names={json.dumps(existing, ensure_ascii=False)}",
            "--var", f"page_anatomy={anatomy}",
            "--var", f"workdir={wd}",
            "--var", f"skills_root={SKILLS_ROOT}",
            "--var", f"content_type={content_type}",
            "--var", f"topic={topic}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"render failed for judge of {kind}: {result.stderr.strip()}"
            )
        prompt_path = prompts_dir / f"{kind}-judge-attempt-{attempt}.md"
        prompt_path.write_text(result.stdout, encoding="utf-8")
        prompts[kind] = str(prompt_path)

    return {
        "prompts": prompts,
        "workdir": str(wd),
        "attempt": attempt,
        "ok": True,
    }


def render_composer_prompt(
    workdir: str | Path,
    schema_path: str | Path,
    context_json: str,
) -> dict:
    """Render the composer prompt into ``<workdir>/prompts/composer.md``.

    The synthesis page anatomy is rendered first (via the same
    ``_render_anatomy`` path the extractor and judge use) and passed
    to the composer prompt as the ``synthesis_anatomy`` template
    variable, so every template under ``templates/`` goes through
    ``render.sh`` uniformly.
    """
    wd = Path(workdir).resolve()
    if not wd.is_dir():
        raise FileNotFoundError(f"workdir not found: {wd}")

    prompts_dir = wd / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    synthesis_anatomy = _render_anatomy("page-anatomy-synthesis.j2")

    template_path = TEMPLATES_DIR / "composer-prompt.j2"
    render_sh = TEMPLATE_SKILL_ROOT / "scripts" / "render.sh"
    cmd = [
        str(render_sh),
        "--template", str(template_path),
        "--var", f"workdir={wd}",
        "--var", f"skills_root={SKILLS_ROOT}",
        "--var", f"context_json={context_json}",
        "--var", f"schema_path={schema_path}",
        "--var", f"synthesis_anatomy={synthesis_anatomy}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"composer prompt render failed: {result.stderr.strip()}"
        )
    prompt_path = prompts_dir / "composer.md"
    prompt_path.write_text(result.stdout, encoding="utf-8")
    return {"prompt": str(prompt_path), "workdir": str(wd), "ok": True}


def _render_anatomy(template_name: str) -> str:
    """Render a page-anatomy jinja template into its embeddable form.

    Anatomy templates live at ``templates/<template_name>`` and carry
    no variables today, but go through ``render.sh`` for two reasons:
    (1) consistency with every other parameterized file in the skill,
    and (2) jinja syntax errors surface here instead of silently
    corrupting the prompt.
    """
    template_path = TEMPLATES_DIR / template_name
    render_sh = TEMPLATE_SKILL_ROOT / "scripts" / "render.sh"
    result = subprocess.run(
        [str(render_sh), "--template", str(template_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"anatomy render failed for {template_name}: "
            f"{result.stderr.strip()}"
        )
    return result.stdout.rstrip()

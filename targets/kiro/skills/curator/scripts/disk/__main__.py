#!/usr/bin/env python3
"""Curator disk tool — typer dispatcher.

Scope: workdir lifecycle, per-item JSON builders, prompt rendering,
verdict aggregation, report-vars. Every canonical JSON artifact the
curator pipeline creates in a workdir is produced through one of
the builders here.

Typer derives the CLI from each command's signature: parameter
names become ``--flags`` (underscores map to dashes), ``Literal``
types become choice constraints, ``Optional`` types become optional
flags, and repeated parameters become ``List[str]``. The handler
body is the only place each command's logic lives — no separate
argparse schema to keep in sync.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Optional

import jsonschema
import typer

from disk import builders, prompts, verdicts, workdir


_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def _load_schema(schema_name: str) -> dict:
    return json.loads((_SCHEMA_DIR / schema_name).read_text())


def _emit(obj) -> None:
    """Print JSON to stdout (one line)."""
    print(json.dumps(obj, ensure_ascii=False))


def _fail(msg: str, **extra) -> None:
    print(json.dumps({"error": msg, **extra}), flush=True)
    raise typer.Exit(code=1)


app = typer.Typer(
    help="Curator disk tool.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # JSON stderr is our error channel
)

workdir_app = typer.Typer(help="Workdir lifecycle", no_args_is_help=True)
app.add_typer(workdir_app, name="workdir")


# ── workdir lifecycle ─────────────────────────────────────

@workdir_app.command("create")
def workdir_create(basename: str) -> None:
    """Create ``/tmp/curator/<date>/<slug>/``; prints the path."""
    wd = workdir.create_workdir(basename)
    print(str(wd))


@workdir_app.command("sweep")
def workdir_sweep(
    path: Annotated[Optional[str], typer.Argument()] = None,
    all_: Annotated[bool, typer.Option("--all")] = False,
) -> None:
    """Delete a specific workdir or every workdir older than the
    stale threshold (``WORKDIR_STALE_DAYS`` in config.py)."""
    _emit(workdir.sweep(path=path, all_stale=all_))


@workdir_app.command("list-stale")
def workdir_list_stale() -> None:
    """List workdirs older than the stale threshold."""
    _emit({"stale": workdir.list_stale()})


# ── prompt rendering ──────────────────────────────────────

@app.command("render-extractor-prompts")
def render_extractor_prompts(
    workdir_path: Annotated[str, typer.Argument(metavar="WORKDIR")],
    source_vault_path: Annotated[str, typer.Option("--source-vault-path")],
    content_type: Annotated[str, typer.Option(
        "--content-type",
        help="Content type from the fetch envelope "
             "(paper|book|article|lecture|talk|podcast|video|movie|"
             "audio|unknown). Drives the per-type summary shape in "
             "the summary-kind extractor prompt. Default: unknown.",
    )] = "unknown",
    topic: Annotated[str, typer.Option(
        "--topic",
        help="Optional topic hint. When non-empty, injected into "
             "every extractor prompt to steer which aspects of a "
             "multi-topic source to prioritize.",
    )] = "",
) -> None:
    """Render all 5 extractor prompts into ``<workdir>/prompts/``."""
    result = prompts.render_all(
        workdir_path, source_vault_path,
        content_type=content_type, topic=topic,
    )
    _emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("render-composer-prompt")
def render_composer_prompt_cmd(
    workdir_path: Annotated[str, typer.Argument(metavar="WORKDIR")],
    schema_path: Annotated[str, typer.Option(
        "--schema-path",
        help="Path to composed.schema.json (absolute or relative "
             "to the skill root).",
    )],
    context_json: Annotated[str, typer.Option(
        "--context-json",
        help="Inline JSON or path to the vault-context JSON blob "
             "produced by `vault.sh context`. Embedded verbatim into "
             "the composer prompt.",
    )],
) -> None:
    """Render the composer prompt into ``<workdir>/prompts/composer.md``.

    Pre-renders the synthesis page anatomy so the composer prompt
    carries the target shape inline — parallels the extractor and
    judge prompt-rendering flow.
    """
    result = prompts.render_composer_prompt(
        workdir_path,
        schema_path=schema_path,
        context_json=context_json,
    )
    _emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("render-retry-extractor-prompt")
def render_retry_extractor_prompt(
    workdir_path: Annotated[str, typer.Argument(metavar="WORKDIR")],
    kind: Annotated[str, typer.Option(
        help="Extractor kind to re-render — one of "
             "summary|sources|keywords|people|models.",
    )],
    source_vault_path: Annotated[str, typer.Option("--source-vault-path")],
    prior_attempt: Annotated[int, typer.Option(
        "--prior-attempt",
        help="Attempt number whose verdicts/<kind>-attempt-<N>.json "
             "the REJECT issues are pulled from.",
    )],
    content_type: Annotated[str, typer.Option(
        "--content-type",
        help="Same content_type value used for the original extractor "
             "wave; drives the per-type summary shape.",
    )] = "unknown",
    topic: Annotated[str, typer.Option(
        "--topic",
        help="Same topic value used for the original extractor wave.",
    )] = "",
) -> None:
    """Re-render one extractor prompt with judge REJECT issues attached.

    Reads the per-attempt verdict file, formats every REJECT verdict's
    issues as markdown, and overwrites ``<wd>/prompts/<kind>.md`` with
    a prompt that carries those issues in a dedicated ``Prior attempt
    issues`` section. Called per failing kind between retry attempts
    so the agent does not have to invent the retry prompt format each
    run.
    """
    try:
        result = prompts.render_retry_one(
            workdir_path, kind, source_vault_path,
            prior_attempt=prior_attempt,
            content_type=content_type, topic=topic,
        )
    except FileNotFoundError as e:
        _fail(str(e))
    except ValueError as e:
        _fail(str(e))
    _emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


@app.command("render-judge-prompts")
def render_judge_prompts(
    workdir_path: Annotated[str, typer.Argument(metavar="WORKDIR")],
    source_vault_path: Annotated[str, typer.Option("--source-vault-path")],
    attempt: Annotated[int, typer.Option()] = 1,
    content_type: Annotated[str, typer.Option(
        "--content-type",
        help="Content type from the fetch envelope. Same set as "
             "render-extractor-prompts. Default: unknown.",
    )] = "unknown",
    topic: Annotated[str, typer.Option(
        "--topic",
        help="Optional topic hint, same value used for the extractor "
             "wave. Lets the judge check that the extractor honored "
             "the hint.",
    )] = "",
) -> None:
    """Render all 5 judge prompts for the given attempt."""
    result = prompts.render_all_judges(
        workdir_path, source_vault_path, attempt=attempt,
        content_type=content_type, topic=topic,
    )
    _emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


# ── verdict aggregation ───────────────────────────────────

_KINDS = ["summary", "sources", "keywords", "people", "models"]


@app.command("aggregate-verdicts")
def aggregate_verdicts(
    workdir_path: Annotated[str, typer.Argument(metavar="WORKDIR")],
    kind: Annotated[str, typer.Option()],
    attempts: Annotated[int, typer.Option()],
    schema_failure: Annotated[Optional[list[str]], typer.Option(
        "--schema-failure",
        help="Record an attempt that failed schema validation; "
             "repeatable as N|MSG. '|' is the delimiter because "
             "schema messages frequently contain ':' (e.g. "
             "'items[0]: missing field')."
    )] = None,
) -> None:
    """Collapse per-attempt judge files into ``<wd>/verdicts/<kind>.json``.

    Enforces the cross-file id-pairing invariant against the paired
    extractor output before writing.
    """
    if kind not in _KINDS:
        _fail(f"--kind must be one of {_KINDS}, got {kind!r}")

    failures = []
    for spec in (schema_failure or []):
        if "|" not in spec:
            _fail(f"--schema-failure expects N|msg, got {spec!r}")
        n_str, msg = spec.split("|", 1)
        try:
            n = int(n_str)
        except ValueError:
            _fail(f"--schema-failure attempt must be int, got {n_str!r}")
        failures.append(verdicts.SchemaFailure(attempt=n, message=msg))

    result = verdicts.aggregate_verdicts(
        workdir_path, kind, attempts_made=attempts, schema_failures=failures)
    _emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


# ── report-vars ───────────────────────────────────────────

_FLAT_BUCKETS = ("keywords", "people", "models", "synthesis",
                 "related_sources")


def _rename_issues_for_report(flat: dict) -> None:
    """Rename ``issues`` → ``_judge_issues`` on every flat item so
    the report template's conditionals render judge concerns as
    ``⚠ judge:`` sub-bullets. The ``issues`` key on composed items
    is written by ``compose-merge-issues``, which is the single
    source of truth after the composer returns.
    """
    for flat_key in _FLAT_BUCKETS:
        for item in flat.get(flat_key, []):
            if item.get("issues"):
                item["_judge_issues"] = item["issues"]


@app.command("report-vars")
def report_vars(
    composed_json: Annotated[str, typer.Argument()],
    output: Annotated[Optional[str], typer.Option("-o", "--output")] = None,
) -> None:
    """Flatten composed.json into the shape ``report.md.j2`` expects.

    Every item whose paired judge verdict carries issues (copied
    onto composed.json by ``compose-merge-issues``) gains a
    ``_judge_issues`` field so the rendered report can surface those
    concerns inline.
    """
    with open(composed_json) as f:
        composed = json.load(f)
    proposals = composed.get("proposals", {}) or {}
    flat = {
        "summary":         composed.get("summary", ""),
        "keywords":        list(proposals.get("keywords", [])),
        "people":          list(proposals.get("people", [])),
        "models":          list(proposals.get("models", [])),
        "synthesis":       list(proposals.get("synthesis", [])),
        "related_sources": list(composed.get("related_sources", [])),
    }
    _rename_issues_for_report(flat)

    schema = _load_schema("report-vars.schema.json")
    if output:
        jsonschema.validate(instance=flat, schema=schema)
        dest = Path(output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        tmp.write_text(json.dumps(flat, ensure_ascii=False, indent=2))
        os.replace(tmp, dest)
        _emit({"path": output, "ok": True})
    else:
        try:
            jsonschema.validate(instance=flat, schema=schema)
        except jsonschema.ValidationError as e:
            _fail(f"report-vars schema violation: {e.message}")
        _emit(flat)


# ── summary / sources / items builders ────────────────────

@app.command("summary-emit")
def summary_emit(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    summary_file: Annotated[str, typer.Option("--summary-file")],
    claim: Annotated[Optional[list[str]], typer.Option(
        "--claim", help="Key claim (repeatable)")] = None,
) -> None:
    """Write ``summary.json`` in a single call (all fields)."""
    _emit(builders.summary_emit(workdir_path, summary_file,
                                claims=claim or []))


@app.command("sources-init")
def sources_init(
    workdir_path: Annotated[str, typer.Option("--workdir")],
) -> None:
    """Create empty ``sources.json``."""
    _emit(builders.sources_init(workdir_path))


@app.command("source-add")
def source_add(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    id: Annotated[str, typer.Option()],
    type: Annotated[str, typer.Option()],
    mention_context: Annotated[str, typer.Option("--mention-context")],
    title: Annotated[Optional[str], typer.Option()] = None,
    authors: Annotated[Optional[list[str]], typer.Option(
        "--authors", help="Author (repeatable)")] = None,
    year: Annotated[Optional[int], typer.Option()] = None,
    arxiv: Annotated[Optional[str], typer.Option()] = None,
    doi: Annotated[Optional[str], typer.Option()] = None,
    isbn: Annotated[Optional[str], typer.Option()] = None,
    url: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Append one entry to ``sources.json``."""
    if type not in ("paper", "book", "url", "video"):
        _fail(f"--type must be paper|book|url|video, got {type!r}")
    _emit(builders.source_add(
        workdir_path, id_=id, type_=type,
        mention_context=mention_context,
        title=title, authors=authors or None,
        year=year, arxiv=arxiv, doi=doi, isbn=isbn, url=url,
    ))


_ITEM_KINDS = ("keyword", "person", "model")


@app.command("items-init")
def items_init(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    kind: Annotated[str, typer.Option()],
) -> None:
    """Create empty ``keywords.json`` / ``people.json`` / ``models.json``."""
    if kind not in _ITEM_KINDS:
        _fail(f"--kind must be one of {_ITEM_KINDS}, got {kind!r}")
    _emit(builders.items_init(workdir_path, kind))


@app.command("item-add")
def item_add(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    kind: Annotated[str, typer.Option()],
    id: Annotated[str, typer.Option()],
    name: Annotated[str, typer.Option()],
    action: Annotated[str, typer.Option()],
    rationale: Annotated[str, typer.Option()],
    match_existing: Annotated[Optional[str], typer.Option("--match-existing")] = None,
    body_file: Annotated[Optional[str], typer.Option("--body-file")] = None,
    frontmatter_file: Annotated[Optional[str], typer.Option("--frontmatter-file")] = None,
    proposed_section: Annotated[Optional[str], typer.Option("--proposed-section")] = None,
    proposed_mode: Annotated[Optional[str], typer.Option("--proposed-mode")] = None,
    frontmatter_delta_file: Annotated[
        Optional[str], typer.Option("--frontmatter-delta-file")] = None,
) -> None:
    """Append one item to ``keywords.json`` / ``people.json`` / ``models.json``."""
    if kind not in _ITEM_KINDS:
        _fail(f"--kind must be one of {_ITEM_KINDS}, got {kind!r}")
    if action not in ("create", "extend"):
        _fail(f"--action must be create|extend, got {action!r}")
    if proposed_mode is not None and proposed_mode not in ("append", "replace"):
        _fail(f"--proposed-mode must be append|replace, got {proposed_mode!r}")
    _emit(builders.item_add(
        workdir_path, kind,
        id_=id, name=name, action=action, rationale=rationale,
        match_existing=match_existing,
        body_file=body_file, frontmatter_file=frontmatter_file,
        proposed_section=proposed_section, proposed_mode=proposed_mode,
        frontmatter_delta_file=frontmatter_delta_file,
    ))


# ── verdict builders ──────────────────────────────────────

_VERDICT_VALUES = ("ACCEPT", "REVIEW", "REJECT")
_SEVERITY_VALUES = ("error", "warning")
_CATEGORY_VALUES = (
    "unsupported_claim", "citation_missing", "citation_mismatch",
    "tone", "anatomy", "naming", "match_existing",
)


@app.command("verdict-init")
def verdict_init(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    kind: Annotated[str, typer.Option()],
    attempt: Annotated[int, typer.Option()],
) -> None:
    """Create empty ``verdicts/<kind>-attempt-<N>.json``."""
    _emit(builders.verdict_init(workdir_path, kind, attempt))


@app.command("verdict-add")
def verdict_add(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    kind: Annotated[str, typer.Option()],
    attempt: Annotated[int, typer.Option()],
    id: Annotated[str, typer.Option()],
    verdict: Annotated[str, typer.Option()],
    rewrite_suggestion: Annotated[
        Optional[str], typer.Option("--rewrite-suggestion")] = None,
) -> None:
    """Append one verdict to a per-attempt file."""
    if verdict not in _VERDICT_VALUES:
        _fail(f"--verdict must be one of {_VERDICT_VALUES}, got {verdict!r}")
    _emit(builders.verdict_add(
        workdir_path, kind, attempt,
        id_=id, verdict=verdict, rewrite_suggestion=rewrite_suggestion,
    ))


@app.command("verdict-add-issue")
def verdict_add_issue(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    kind: Annotated[str, typer.Option()],
    attempt: Annotated[int, typer.Option()],
    id: Annotated[str, typer.Option()],
    severity: Annotated[str, typer.Option()],
    category: Annotated[str, typer.Option()],
    message: Annotated[str, typer.Option()],
    location: Annotated[Optional[str], typer.Option()] = None,
    source_evidence: Annotated[Optional[str], typer.Option("--source-evidence")] = None,
) -> None:
    """Append an issue to an existing verdict item."""
    if severity not in _SEVERITY_VALUES:
        _fail(f"--severity must be one of {_SEVERITY_VALUES}, got {severity!r}")
    if category not in _CATEGORY_VALUES:
        _fail(f"--category must be one of {_CATEGORY_VALUES}, got {category!r}")
    _emit(builders.verdict_add_issue(
        workdir_path, kind, attempt,
        id_=id, severity=severity, category=category, message=message,
        location=location, source_evidence=source_evidence,
    ))


# ── composed-* builders ───────────────────────────────────

_SOURCE_TYPES = ("pdf", "epub", "article", "video", "unknown")
_RELATED_TYPES = ("paper", "book", "url", "video")


@app.command("composed-init")
def composed_init(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    source_path: Annotated[str, typer.Option("--source-path")],
    source_type: Annotated[str, typer.Option("--source-type")],
    source_basename: Annotated[str, typer.Option("--source-basename")],
) -> None:
    """Create the ``composed.json`` skeleton (source + empty lists)."""
    if source_type not in _SOURCE_TYPES:
        _fail(f"--source-type must be one of {_SOURCE_TYPES}, got {source_type!r}")
    _emit(builders.composed_init(
        workdir_path, source_path, source_type, source_basename,
    ))


@app.command("composed-set-summary")
def composed_set_summary(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    summary_file: Annotated[str, typer.Option("--summary-file")],
) -> None:
    """Set composed.json's ``summary`` field from a file."""
    _emit(builders.composed_set_summary(workdir_path, summary_file))


_COMPOSED_ITEM_KINDS = ("keyword", "person", "model", "synthesis")


@app.command("composed-add")
def composed_add(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    kind: Annotated[str, typer.Option(
        help="keyword|person|model|synthesis")],
    id: Annotated[str, typer.Option()],
    action: Annotated[str, typer.Option()],
    rationale: Annotated[str, typer.Option()],
    body_file: Annotated[str, typer.Option("--body-file")],
    frontmatter_file: Annotated[str, typer.Option("--frontmatter-file")],
    name: Annotated[Optional[str], typer.Option(
        help="Required for keyword|person|model")] = None,
    path: Annotated[Optional[str], typer.Option(
        help="Required for synthesis")] = None,
    match_existing: Annotated[Optional[str], typer.Option(
        "--match-existing",
        help="Only for keyword|person|model")] = None,
) -> None:
    """Append a reconciled entity or planned synthesis page to composed.json.

    keyword|person|model pass ``--name`` (and optional
    ``--match-existing``); synthesis passes ``--path``. Other flags
    are identical across kinds.
    """
    if kind not in _COMPOSED_ITEM_KINDS:
        _fail(f"--kind must be one of {_COMPOSED_ITEM_KINDS}, got {kind!r}")
    if action not in ("create", "extend"):
        _fail(f"--action must be create|extend, got {action!r}")

    if kind == "synthesis":
        if path is None:
            _fail("--path is required when --kind=synthesis")
        if name is not None:
            _fail("--name is not accepted when --kind=synthesis")
        if match_existing is not None:
            _fail("--match-existing is not accepted when --kind=synthesis")
        _emit(builders.composed_add_synthesis(
            workdir_path, id_=id, path_=path,
            action=action, rationale=rationale,
            body_file=body_file, frontmatter_file=frontmatter_file,
        ))
        return

    # keyword | person | model
    if name is None:
        _fail(f"--name is required when --kind={kind}")
    if path is not None:
        _fail(f"--path is not accepted when --kind={kind}")
    _emit(builders.composed_add_entity(
        workdir_path, kind,
        id_=id, name=name, action=action, rationale=rationale,
        match_existing=match_existing,
        body_file=body_file, frontmatter_file=frontmatter_file,
    ))


@app.command("composed-add-related-source")
def composed_add_related_source(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    type: Annotated[str, typer.Option()],
    title: Annotated[str, typer.Option()],
    reason: Annotated[str, typer.Option()],
    authors: Annotated[Optional[list[str]], typer.Option("--authors")] = None,
    year: Annotated[Optional[int], typer.Option()] = None,
    arxiv: Annotated[Optional[str], typer.Option()] = None,
    doi: Annotated[Optional[str], typer.Option()] = None,
    isbn: Annotated[Optional[str], typer.Option()] = None,
    url: Annotated[Optional[str], typer.Option()] = None,
) -> None:
    """Append a follow-up source suggestion to composed.json."""
    if type not in _RELATED_TYPES:
        _fail(f"--type must be one of {_RELATED_TYPES}, got {type!r}")
    _emit(builders.composed_add_related_source(
        workdir_path, type_=type, title=title, reason=reason,
        authors=authors or None, year=year,
        arxiv=arxiv, doi=doi, isbn=isbn, url=url,
    ))


@app.command("compose-merge-issues")
def compose_merge_issues(
    workdir_path: Annotated[str, typer.Argument(metavar="WORKDIR")],
) -> None:
    """Copy REVIEW-verdict issues from ``verdicts/<agent>.json`` onto
    paired items in ``composed.json``. Idempotent: repeating the call
    does not duplicate issues. Raises if a verdict id has no matching
    item in composed.json.
    """
    try:
        result = builders.compose_merge_issues(workdir_path)
    except FileNotFoundError as e:
        _fail(str(e))
    except ValueError as e:
        _fail(str(e))
    _emit(result)


# ── approved-* builders ───────────────────────────────────

_APPROVED_ACTIONS = ("approve", "edit", "deny", "rename", "redirect")


@app.command("approved-init")
def approved_init(
    workdir_path: Annotated[str, typer.Option("--workdir")],
) -> None:
    """Create empty ``approved.json`` (workdir + decisions:[])."""
    _emit(builders.approved_init(workdir_path))


@app.command("approved-add-decision")
def approved_add_decision(
    workdir_path: Annotated[str, typer.Option("--workdir")],
    id: Annotated[str, typer.Option()],
    action: Annotated[str, typer.Option()],
    override_body_file: Annotated[
        Optional[str], typer.Option("--override-body-file")] = None,
    override_frontmatter_file: Annotated[
        Optional[str], typer.Option("--override-frontmatter-file")] = None,
    override_path: Annotated[
        Optional[str], typer.Option("--override-path")] = None,
    override_section: Annotated[
        Optional[str], typer.Option("--override-section")] = None,
    override_mode: Annotated[
        Optional[str], typer.Option("--override-mode")] = None,
    new_name: Annotated[Optional[str], typer.Option("--new-name")] = None,
) -> None:
    """Append one user decision to approved.json."""
    if action not in _APPROVED_ACTIONS:
        _fail(f"--action must be one of {_APPROVED_ACTIONS}, got {action!r}")
    if override_mode is not None and override_mode not in ("append", "replace"):
        _fail(f"--override-mode must be append|replace, got {override_mode!r}")
    _emit(builders.approved_add_decision(
        workdir_path, id_=id, action=action,
        override_body_file=override_body_file,
        override_frontmatter_file=override_frontmatter_file,
        override_path=override_path,
        override_section=override_section,
        override_mode=override_mode,
        new_name=new_name,
    ))


if __name__ == "__main__":
    app()

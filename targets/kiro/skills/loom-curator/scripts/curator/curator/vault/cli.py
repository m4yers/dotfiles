"""Typer CLI surface for the vault subpackage.

Mounts:
    vault match              → match.build_match
    vault replica build      → replica.build_replica
    vault replica apply      → replica.apply_replica

All CLI output is YAML on stdout (the task-runner contract).
"""
from __future__ import annotations

from typing import Annotated, Optional

import typer

from curator.utils import emit, fail
from curator.vault.match import build_match
from curator.vault.replica import (
    apply_replica,
    build_replica,
    build_report,
    prune_replica,
    strip_dead_links,
)


# ── match ───────────────────────────────────────────────


def cli_match(
    keywords: Annotated[Optional[str], typer.Option(
        "--keywords", help="Path to keywords/output.yaml")] = None,
    people: Annotated[Optional[str], typer.Option(
        "--people", help="Path to people/output.yaml")] = None,
    models: Annotated[Optional[str], typer.Option(
        "--models", help="Path to models/output.yaml")] = None,
) -> None:
    """Match extracted items against existing vault pages.

    For each (kind, path) pair, reads the extractor output and
    emits a per-kind list of ``{name, match}`` entries.
    """
    inputs: dict[str, str] = {}
    if keywords: inputs["keywords"] = keywords
    if people:   inputs["people"]   = people
    if models:   inputs["models"]   = models
    if not inputs:
        fail("at least one of --keywords / --people / --models is required")
    emit(build_match(inputs))


# ── replica ─────────────────────────────────────────────


def cli_replica_build(
    workdir: Annotated[str, typer.Argument(
        help="Run workdir; reads each extract-<kind>/output.yaml + "
             "vault-match outputs, writes "
             "<wd>/vault-replica/<vault_path> + manifest.yaml.")],
) -> None:
    """Build the workdir replica from the per-kind extractor
    outputs.

    Reads each ``extract-<kind>/output.yaml`` directly + the
    optional ``vault-match`` task's hits, and renders one file
    per artifact-mode item into
    ``<wd>/vault-replica/<vault_path>``. ``extract-summary`` is
    skipped — its output is summary text, not an item list, and
    summaries don't get standalone vault pages.

    Synthesis hubs are NOT built here — the synthesis agent task
    runs after this and writes its pages directly into the
    replica.
    """
    from pathlib import Path as _Path
    import yaml as _yaml
    from loom.engine import store
    from curator import quintet as q_mod

    wd = _Path(workdir).resolve()
    plan = store.load_plan(wd)

    # Per-kind extractions: read every extract-<kind>/output.yaml
    # except extract-summary (string payload, not items).
    extractions: dict = {}
    for task in plan.tasks:
        if not task.id.startswith("extract-"):
            continue
        kind = task.id[len("extract-"):]
        if kind == "summary":
            continue
        out_path = store.task_output_path(wd, plan, task.id)
        if not out_path.exists():
            continue
        loaded = _yaml.safe_load(out_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            continue
        items = loaded.get(kind)
        if isinstance(items, list):
            extractions[kind] = items

    # Per-kind destinations from quintet.yaml's rule table. Drives
    # the artifact-vs-synthesis filter inside build_replica.
    destinations = {
        kind: q_mod.destination_for(kind) or {"mode": "synthesis"}
        for kind in extractions.keys()
    }

    # vault-match output is optional. When present, build_replica
    # uses it to catch alias hits a path-existence check would
    # miss.
    vault_matches: dict | None = None
    if "vault-match" in plan.ids():
        vm_path = store.task_output_path(wd, plan, "vault-match")
        if vm_path.exists():
            loaded = _yaml.safe_load(vm_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                vault_matches = loaded

    # Source basename for the replica's source-tracking — the
    # build only uses it to derive a default filename slug for
    # any kind that ever needs source attribution.
    fetch_path = store.task_output_path(wd, plan, "fetch") \
        if "fetch" in plan.ids() else None
    basename = "unknown-source"
    if fetch_path and fetch_path.exists():
        try:
            fdata = _yaml.safe_load(fetch_path.read_text(encoding="utf-8"))
            if isinstance(fdata, dict) and fdata.get("basename"):
                basename = str(fdata["basename"])
        except Exception:
            pass

    try:
        result = build_replica(
            wd, extractions, destinations, vault_matches, basename)
    except Exception as e:
        fail(f"build-replica failed: {e}")
    emit(result)


def cli_replica_apply(
    workdir: Annotated[str, typer.Argument(
        help="Run workdir; reads <wd>/vault-replica/ and writes "
             "every tracked file to the vault via pages.save.")],
) -> None:
    """Apply the workdir replica to the vault.

    Walks ``<wd>/vault-replica/`` against ``manifest.yaml``. Files
    the user deleted between build and apply are skipped with
    ``user_deleted`` reason — that is the rejection mechanism.
    Untracked files (present on disk, missing from manifest) are
    flagged as failures so silent additions do not slip through.
    """
    from pathlib import Path as _Path
    wd = _Path(workdir).resolve()
    result = apply_replica(wd)
    emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


def cli_replica_prune(
    workdir: Annotated[str, typer.Argument(
        help="Run workdir; reads synthesis hubs from "
             "<wd>/vault-replica/21 WIKI/, prunes manifest "
             "entries whose op=create name is not wikilinked.")],
) -> None:
    """Prune unreferenced new artifact pages from the replica.

    Scans every ``<wd>/vault-replica/21 WIKI/*.md`` for
    wikilinks (body + frontmatter). For each manifest entry:

    - ``op: modified`` → kept (vault already has the page).
    - ``op: create`` whose name is wikilinked → kept.
    - ``op: create`` whose name is NOT wikilinked → replica file
      deleted, manifest entry removed.

    Surfaces ``orphan_links`` — wikilink targets that match
    neither a surviving artifact nor an existing vault page;
    these will render as broken links in Obsidian.
    """
    from pathlib import Path as _Path
    wd = _Path(workdir).resolve()
    try:
        result = prune_replica(wd)
    except FileNotFoundError as e:
        fail(str(e))
    emit(result)


def cli_replica_strip_dead_links(
    workdir: Annotated[str, typer.Argument(
        help="Run workdir; rewrites dead [[wikilinks]] in "
             "<wd>/vault-replica/21 WIKI/*.md to plain text "
             "after the human gate.")],
) -> None:
    """Strip dead wikilinks from synthesis hubs after the gate.

    The user may delete replica files at the gate. References to
    those deletions become broken links in Obsidian. This step
    rewrites every dead ``[[Target]]`` (and ``[[Target|Alias]]``)
    in synthesis hubs to plain text, preserving alias visible
    text and intra-page anchor links.

    Resolution: a target is alive when a ``.md`` file is present
    in the post-gate replica OR an existing vault page matches
    via the prune-replica helper.
    """
    from pathlib import Path as _Path
    wd = _Path(workdir).resolve()
    try:
        result = strip_dead_links(wd)
    except FileNotFoundError as e:
        fail(str(e))
    emit(result)


# ── report ──────────────────────────────────────────────


def cli_report(
    workdir: Annotated[str, typer.Argument(
        help="Run workdir; reads upstream task outputs + synthesis "
             "paths and writes <wd>/vault-replica/_REPORT.md.")],
) -> None:
    """Render the gate operator's overview report.

    Reads classify (quintet/topic), extract-summary (verbatim
    summary text), each ``extract-<kind>``'s items (counts +
    names), and the synthesis task's emitted paths. Writes a
    single Markdown file into the replica root for the gate to
    open first.
    """
    from pathlib import Path as _Path
    wd = _Path(workdir).resolve()
    try:
        result = build_report(wd)
    except Exception as e:
        fail(f"build-report failed: {e}")
    emit(result)


# ── typer app assembly ──────────────────────────────────


replica_app = typer.Typer(
    help="Workdir vault-replica build + apply.",
    no_args_is_help=True,
)
replica_app.command("build")(cli_replica_build)
replica_app.command("apply")(cli_replica_apply)
replica_app.command("prune")(cli_replica_prune)
replica_app.command("strip-dead-links")(cli_replica_strip_dead_links)


app = typer.Typer(
    help="Curator vault management.",
    no_args_is_help=True,
)
app.command("match")(cli_match)
app.command("report")(cli_report)
app.add_typer(replica_app, name="replica")

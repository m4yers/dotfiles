"""Vault replica — workdir mirror of the proposed vault state.

Replaces the legacy materialize → apply_plan → verify_batch chain
with a flatter two-step flow:

1. ``build_replica`` reads the compose-merge + compose-synthesis
   outputs, decides per-item whether the target vault page already
   exists, and writes the resulting page (fresh OR
   merged-with-existing) to ``<workdir>/vault-replica/<vault_path>``.
   Also writes a ``manifest.yaml`` at the replica root listing every
   file and its op (``create`` or ``modified``); modified entries
   carry the absolute path of the vault original so the gate's diff
   view can compare against it.

2. ``apply_replica`` walks the replica, validates each file via the
   existing ``vault.pages.save`` pipeline (scope check + atomic
   write), and records per-path outcomes. Files the user deleted
   from the replica between build and apply are skipped with
   ``status=user_deleted`` — that is the rejection mechanism;
   no separate decisions YAML is needed.

The replica is the single source of truth for what will land in the
vault. The human gate runs between build and apply; reviewers can
inspect, edit, or delete files in the replica via their editor.
"""
from __future__ import annotations
import datetime
import json
import os
import subprocess
import tempfile
from pathlib import Path

import yaml

from curator.vault.config import (
    SOURCES_DIR,
    SYNTHESIS_DIR,
)
from curator.vault.pages import (
    abs_path,
    parse,
    require_writable,
    rel_path as vault_rel_path,
    save,
    slugify_basename,
)


# Locations of the per-kind ``page.j2`` templates and the shared
# render.sh shim (lives in the ``template`` skill).
# replica.py is at <curator>/scripts/curator/vault/replica.py;
# four .parent hops reach the skill root.
_SKILL_ROOT    = Path(__file__).resolve().parent.parent.parent.parent
_TEMPLATES_DIR = _SKILL_ROOT / "templates"
_VAULT_TEMPLATES_DIR = _TEMPLATES_DIR / "vault"
_RENDER_SH     = (Path(os.environ.get(
    "SKILLS", str(Path.home() / ".kiro/skills"))) /
    "home" / "template" / "scripts" / "render.sh")


# Map extractor kind names → vault page type. The template name
# is the type (e.g. ``person.j2``); multiple kinds collapse to
# the same template.
_KIND_TO_TYPE = {
    "keywords":  "keyword",
    "people":    "person",
    "models":    "model",
    "authors":   "person",
    "guests":    "person",
    "speaker":   "person",
    "quotes":    "quote",
}


# ── page-edit helpers ───────────────────────────────────
#
# Inlined from the former ``vault/ops.py`` since replica is the
# only caller. Apply-replica calls
# ``_ensure_required_frontmatter`` against every replica file
# before saving to the vault, so a page edited by the gate
# operator that drops the required ``type`` field fails fast.

# Frontmatter fields every replica page must declare.
_REQUIRED_FIELDS = ("type",)


def _ensure_required_frontmatter(fm: dict):
    """Page frontmatter must declare ``type:`` so the vault can
    classify it. Raise ValueError if missing."""
    for f in _REQUIRED_FIELDS:
        if f not in fm:
            raise ValueError(
                f"frontmatter missing required field: {f}")


# ── replica root layout ─────────────────────────────────

# Subdir under the workdir that mirrors the vault's structure for
# the proposed pages. The gate operator browses + edits files here.
_REPLICA_DIRNAME = "vault-replica"
_MANIFEST_NAME   = "manifest.yaml"
_REPORT_NAME     = "_REPORT.md"

# Files under the replica root that are NOT vault content. Apply
# skips them rather than treating them as untracked.
_INTERNAL_FILES = frozenset({_MANIFEST_NAME, _REPORT_NAME})


# ── public helpers ──────────────────────────────────────


def _replica_root(workdir: Path) -> Path:
    """Path of the replica directory inside a workdir."""
    return Path(workdir) / _REPLICA_DIRNAME


def _manifest_path(workdir: Path) -> Path:
    """Path of the manifest.yaml inside a workdir's replica."""
    return _replica_root(workdir) / _MANIFEST_NAME


# ── build ───────────────────────────────────────────────


def build_replica(
    workdir: Path,
    extractions: dict,
    destinations: dict,
    vault_matches: dict[str, dict[str, str | None]] | None,
    source_basename: str,
) -> dict:
    """Populate ``<workdir>/vault-replica/`` with atomic pages
    from the per-kind extractor outputs.

    Synthesis pages are NOT built here — the synthesis agent task
    runs after build-replica and writes its pages directly into
    the replica.

    Inputs:

    - ``extractions``  — ``{kind: [items]}`` from each
      ``extract-<kind>/output.yaml``.
    - ``destinations`` — ``{kind: {mode, folder}}`` from
      quintet.yaml. Filters which kinds become artifact pages.
    - ``vault_matches`` — optional ``vault-match`` output, used
      to catch alias hits that a path-existence check would miss.
    - ``source_basename`` — the source's basename, used by templates
      that emit source-attribution metadata (today: none of the
      atomic templates use it; kept for future kinds).

    Returns ``{replica_root, manifest_path, entries}``.
    """
    rr = _replica_root(workdir)
    rr.mkdir(parents=True, exist_ok=True)

    # Wipe per-kind artifact folders so a re-run produces a clean
    # set of atomic pages. Synthesis pages live under
    # ``21 SYNTHESIS/`` and are authored by a downstream agent
    # task, NOT by build-replica — they are deliberately preserved
    # across re-runs so the agent's work is not destroyed by a
    # mechanical rebuild.
    import shutil
    artifact_folders = {
        dest.get("folder")
        for dest in destinations.values()
        if dest.get("mode") == "artifact" and dest.get("folder")
    }
    for fp in artifact_folders:
        target = rr / fp
        if target.exists():
            shutil.rmtree(target)

    entries: list[dict] = []

    # Build a per-kind name → existing-vault-path index from the
    # vault_matches input. The matcher catches alias matches that
    # a path-only existence check would miss.
    vm_index: dict[str, dict[str, str]] = {}
    for kind, items in (vault_matches or {}).items():
        if not isinstance(items, list):
            continue
        sub: dict[str, str] = {}
        for it in items:
            if not isinstance(it, dict):
                continue
            name = it.get("name")
            match = it.get("match")
            if isinstance(name, str) and isinstance(match, str):
                sub[_normalize(name)] = match
        if sub:
            vm_index[kind] = sub

    for kind, items in extractions.items():
        dest = destinations.get(kind) or {}
        if dest.get("mode") != "artifact":
            continue
        folder = dest.get("folder")
        if not folder:
            continue
        if not items:
            continue
        for item in items:
            entry = _build_atomic_page(
                rr, kind, item, folder, source_basename,
                vm_index.get(kind, {}))
            if entry is not None:
                entries.append(entry)

    manifest = {"entries": entries,
                "source_basename": source_basename,
                "built_at": datetime.datetime.utcnow().isoformat(
                    timespec="seconds") + "Z"}
    _manifest_path(workdir).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True),
        encoding="utf-8")

    return {
        "replica_root":  str(rr),
        "manifest_path": str(_manifest_path(workdir)),
        "entries":       entries,
    }


def _normalize(name: str) -> str:
    """Lowercase + collapse whitespace for fuzzy name matching."""
    return " ".join(name.lower().split())


def _build_atomic_page(
    rr: Path,
    kind: str,
    item: dict,
    folder: str,
    source_basename: str,
    name_to_existing_path: dict[str, str],
) -> dict | None:
    """Build one atomic page (keyword/person/model/etc.) into the
    replica using the kind's vault-type template.

    Both branches render the page through the template and
    overwrite the replica path. The ``op`` distinction (create
    vs modified) is informational — it tells the gate operator
    whether a vault original exists to diff against.

    Returns the manifest entry, or None if the item lacks a
    name or the kind has no vault-type template.
    """
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    if not _kind_has_page_template(kind):
        return None

    # Filename uses the natural name verbatim (with filesystem-
    # illegal chars stripped). Obsidian resolves
    # ``[[Natural Name]]`` wikilinks against this filename
    # directly — no aliases needed.
    filename = slugify_basename(name) or "item"
    canonical_path = f"{folder}/{filename}.md"

    # Prefer the matcher's hit (catches alias matches with a
    # different stem); fall back to the canonical path.
    matched = name_to_existing_path.get(_normalize(name))
    vault_path = matched or canonical_path
    replica_file = rr / vault_path
    replica_file.parent.mkdir(parents=True, exist_ok=True)

    rendered = _render_page_via_template(kind, item)
    replica_file.write_text(rendered, encoding="utf-8")

    existing_abs = abs_path(vault_path)
    if existing_abs.exists():
        return {
            "vault_path":     vault_path,
            "op":             "modified",
            "kind":           kind,
            "name":           name,
            "original_path":  str(existing_abs),
        }
    return {
        "vault_path": vault_path,
        "op":         "create",
        "kind":       kind,
        "name":       name,
    }


def _kind_has_page_template(kind: str) -> bool:
    """True iff a vault-page template exists for the kind's
    type. Build-replica skips kinds without a template — the
    curator has nothing to render for them yet."""
    type_name = _KIND_TO_TYPE.get(kind)
    if type_name is None:
        return False
    return (_VAULT_TEMPLATES_DIR / f"{type_name}.j2").exists()


def _render_page_via_template(kind: str, item: dict) -> str:
    """Render a vault page through the kind's type template at
    ``templates/vault/<type>.j2``. Returns the rendered markdown
    (frontmatter + body) ready to write to disk.
    """
    type_name = _KIND_TO_TYPE.get(kind)
    if type_name is None:
        raise ValueError(f"no vault type mapping for kind {kind!r}")
    template_path = _VAULT_TEMPLATES_DIR / f"{type_name}.j2"
    variables = {
        "item":  item,
        "today": datetime.date.today().isoformat(),
    }

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
                "--template",    str(template_path),
                "--include-dir", str(_VAULT_TEMPLATES_DIR),
                "--json-vars",   vars_file,
                "--allow-unused",
            ],
            capture_output=True, text=True, check=True, env=env,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"vault/{type_name}.j2 render for kind {kind!r} failed: "
            f"{(e.stderr or '').strip() or e}") from e
    finally:
        Path(vars_file).unlink(missing_ok=True)
    # Strip leading whitespace from the rendered output — the
    # template's opening ``{# comment #}`` block introduces a
    # newline before the YAML frontmatter ``---`` delimiter,
    # which trips the strict frontmatter parser.
    return proc.stdout.lstrip()


# ── report ──────────────────────────────────────────────


def build_report(workdir: Path) -> dict:
    """Render the gate operator's overview ``_REPORT.md`` into the
    replica root.

    Reads upstream task outputs directly:
    - classify's quintet + topic
    - extract-summary's summary text (pasted verbatim)
    - each ``extract-<kind>``'s items (kind name + count + names)
    - the synthesis task's emitted paths

    Writes to ``<wd>/vault-replica/_REPORT.md``. Listed in
    ``_INTERNAL_FILES`` so apply-replica skips it.
    """
    from engine import store
    plan = store.load_plan(workdir)

    classify = _safe_load(workdir, "classify", plan)
    quintet  = (classify or {}).get("quintet") or {}
    topic    = (classify or {}).get("topic") or "(untyped)"

    summary_doc = _safe_load(workdir, "extract-summary", plan)
    summary = ((summary_doc or {}).get("summary") or "").strip()

    extractions: dict[str, list[dict]] = {}
    for task in plan.tasks:
        if not task.id.startswith("extract-"):
            continue
        kind = task.id[len("extract-"):]
        if kind == "summary":
            continue
        out = _safe_load(workdir, task.id, plan) or {}
        items = out.get(kind)
        if isinstance(items, list):
            # Keep only items with a usable identifier so the
            # report's name list is meaningful.
            extractions[kind] = [
                it for it in items
                if isinstance(it, dict) and it.get("name")
            ]

    synthesis_doc = _safe_load(workdir, "synthesis", plan)
    synthesis_paths = ((synthesis_doc or {}).get("paths") or [])

    fetch_doc = _safe_load(workdir, "fetch", plan)
    basename  = ((fetch_doc or {}).get("basename")
                 or "unknown-source")

    # Files in this run that overwrite existing vault pages. Two
    # sources: manifest entries with op=modified (extractor
    # artifacts that matched an existing page) and synthesis pages
    # whose replica path also exists in the vault. The report
    # enumerates both so the gate operator sees every overwrite up
    # front (the editor only opens these as diffs; new pages are
    # listed but not opened).
    manifest_modifications: list[dict] = []
    manifest = _load_manifest(workdir) or {}
    for entry in manifest.get("entries") or []:
        if entry.get("op") != "modified":
            continue
        vp = entry.get("vault_path")
        if not isinstance(vp, str):
            continue
        manifest_modifications.append({
            "vault_path": vp,
            "kind":       entry.get("kind") or "",
            "name":       entry.get("name") or vp,
        })

    synthesis_modifications: list[dict] = []
    rr = _replica_root(workdir)
    synth_dir = rr / SYNTHESIS_DIR
    if synth_dir.exists():
        for entry in sorted(synth_dir.iterdir()):
            if not entry.is_file() or entry.suffix != ".md":
                continue
            rel = f"{SYNTHESIS_DIR}/{entry.name}"
            if abs_path(rel).exists():
                synthesis_modifications.append({
                    "vault_path": rel,
                    "name":       entry.stem,
                })

    rendered = _render_report_via_template(
        basename, topic, quintet, summary,
        extractions, synthesis_paths,
        manifest_modifications, synthesis_modifications)

    rendered = _mdformat_wrap(rendered, width=80)

    rr = _replica_root(workdir)
    rr.mkdir(parents=True, exist_ok=True)
    out_path = rr / _REPORT_NAME
    out_path.write_text(rendered, encoding="utf-8")

    return {"report_path": str(out_path)}


def _mdformat_wrap(markdown: str, *, width: int) -> str:
    """Pass ``markdown`` through ``mdformat --wrap=<width>`` and
    return the formatted output.

    If mdformat is unavailable or errors out, fall back to the
    unformatted input — the report is informational and a missing
    formatter must not abort the run.
    """
    try:
        proc = subprocess.run(
            ["mdformat", "--wrap", str(width), "-"],
            input=markdown, capture_output=True, text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return markdown
    return proc.stdout


def _safe_load(workdir: Path, task_id: str, plan) -> dict | None:
    """Read a task's output.yaml; return None if missing or
    unparseable. Defensive — the report should never abort
    because a single upstream is malformed."""
    if task_id not in plan.ids():
        return None
    from engine import store
    p = store.task_output_path(workdir, task_id, plan=plan)
    if not p.exists():
        return None
    try:
        loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _render_report_via_template(
    basename: str,
    topic: str,
    quintet: dict,
    summary: str,
    extractions: dict[str, list[dict]],
    synthesis_paths: list[str],
    manifest_modifications: list[dict],
    synthesis_modifications: list[dict],
) -> str:
    """Render ``templates/report.md.j2`` via the shared render.sh
    shim. Returns the rendered markdown."""
    template_path = _SKILL_ROOT / "templates" / "report.md.j2"
    variables = {
        "basename":        basename,
        "topic":           topic,
        "quintet":         quintet,
        "summary":         summary,
        "extractions":     extractions,
        "synthesis_paths": synthesis_paths,
        "manifest_modifications":  manifest_modifications,
        "synthesis_modifications": synthesis_modifications,
    }

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
                "--template",    str(template_path),
                "--include-dir", str(_SKILL_ROOT / "templates"),
                "--json-vars",   vars_file,
                "--allow-unused",
            ],
            capture_output=True, text=True, check=True, env=env,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"report.md.j2 render failed: "
            f"{(e.stderr or '').strip() or e}") from e
    finally:
        Path(vars_file).unlink(missing_ok=True)
    return proc.stdout.lstrip()


# ── apply ───────────────────────────────────────────────


def apply_replica(workdir: Path) -> dict:
    """Walk the replica and write each file to the vault.

    Per-file outcomes:

    - manifest entry + replica file present → validated, saved,
      ``ok: True``.
    - manifest entry + replica file absent → user deleted before
      applying. ``skipped: True, reason: "user_deleted"``.
    - replica file present but missing from manifest → typically a
      synthesis page the synthesis agent wrote directly; treated
      as ``op: create`` (or ``op: modified`` if the vault already
      has that path) and validated against ``pages.save``.

    Returns ``{ok, results}`` where ``ok`` is true only if every
    file applied or was deliberately user-deleted.
    """
    rr = _replica_root(workdir)
    if not rr.exists():
        return {"ok": False, "results": [],
                "error": f"replica missing at {rr}"}

    manifest = _load_manifest(workdir)
    if manifest is None:
        return {"ok": False, "results": [],
                "error": f"manifest missing at {_manifest_path(workdir)}"}

    tracked_paths: set[str] = set()
    results: list[dict] = []

    for entry in manifest.get("entries") or []:
        vault_path = entry.get("vault_path")
        if not isinstance(vault_path, str):
            continue
        tracked_paths.add(vault_path)

        replica_file = rr / vault_path
        if not replica_file.exists():
            results.append({
                "vault_path": vault_path,
                "skipped":    True,
                "reason":     "user_deleted",
            })
            continue

        try:
            require_writable(vault_path)
            raw = replica_file.read_text(encoding="utf-8")
            fm, body = parse(raw)
            _ensure_required_frontmatter(fm)
            fm["last_updated"] = datetime.date.today().isoformat()
            save(vault_path, fm, body)
            results.append({
                "vault_path": vault_path,
                "ok":         True,
                "op":         entry.get("op"),
            })
        except (ValueError, FileNotFoundError, PermissionError) as e:
            results.append({
                "vault_path": vault_path,
                "ok":         False,
                "error":      str(e),
            })

    # Untracked files — replica files with no manifest entry.
    # Synthesis pages (under ``21 SYNTHESIS/``) are expected here:
    # the synthesis agent writes them directly via fs_write rather
    # than going through the build-replica manifest. Validate +
    # apply them just like tracked entries; vault-state decides
    # ``op`` (create vs modified).
    #
    # Untracked files OUTSIDE ``21 SYNTHESIS/`` are flagged as
    # failures so non-synthesis content cannot slip past
    # build-replica's validation.
    for f in _walk_replica_files(rr):
        rel = str(f.relative_to(rr))
        if rel in _INTERNAL_FILES or rel in tracked_paths:
            continue
        if not rel.startswith(SYNTHESIS_DIR + "/"):
            results.append({
                "vault_path": rel,
                "ok":         False,
                "error":      "untracked file (no manifest entry)",
            })
            continue

        # Synthesis page: validate + save. Op is determined by
        # whether the vault already has the path (synthesis hubs
        # are usually new, but we don't assume).
        try:
            require_writable(rel)
            raw = f.read_text(encoding="utf-8")
            fm, body = parse(raw)
            _ensure_required_frontmatter(fm)
            fm["last_updated"] = datetime.date.today().isoformat()
            op = ("modified" if abs_path(rel).exists()
                  else "create")
            save(rel, fm, body)
            results.append({
                "vault_path": rel,
                "ok":         True,
                "op":         op,
                "kind":       "synthesis",
            })
        except (ValueError, FileNotFoundError, PermissionError) as e:
            results.append({
                "vault_path": rel,
                "ok":         False,
                "error":      str(e),
            })

    ok = all(r.get("ok") or r.get("skipped") for r in results)
    return {"ok": ok, "results": results}


def _load_manifest(workdir: Path) -> dict | None:
    p = _manifest_path(workdir)
    if not p.exists():
        return None
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def _walk_replica_files(root: Path) -> list[Path]:
    """Every file under the replica root, sorted for determinism.
    Hidden files (dotfiles) are skipped."""
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in
                path.relative_to(root).parts):
            continue
        out.append(path)
    return out

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
    # ``21 WIKI/`` and are authored by a downstream agent
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


# ── per-kind display name ───────────────────────────────
#
# Different extractor schemas use different identity fields:
# ``name`` (keywords, models, people, topics, themes, …),
# ``title`` (citations, chapters, code_examples), ``summary``
# (key_points), ``claim`` (contributions, results), ``prompt``
# (exercises), ``text`` (quotes). Both the report and the
# atomic-page builder need ONE call to pick the right field per
# kind — otherwise items silently disappear from the report and
# from manifests because the code defaulted to ``item['name']``.

# Per-kind text fields that should be truncated to a one-liner
# label when no explicit name/title exists.
_KIND_TEXT_LABEL = {
    "key_points":     "summary",
    "contributions":  "claim",
    "results":        "claim",
    "exercises":      "prompt",
    "quotes":         "text",
}


def _truncate_label(s: str, max_chars: int = 80) -> str:
    """Reduce a multi-line text field to a single-line label.

    First sentence wins if it's short enough; otherwise truncate
    at the last whitespace before ``max_chars`` and append ``…``.

    A "sentence end" is a period followed by whitespace + uppercase
    letter (or end-of-string). This avoids breaking on abbreviations
    like ``vs.``, ``e.g.``, ``i.e.``, or ``Mr.``.
    """
    s = (s or "").split("\n", 1)[0].strip()
    if not s:
        return ""
    # Sentence end: period + whitespace + uppercase letter.
    m = _SENTENCE_END_RE.search(s)
    if m and m.start() + 1 <= max_chars:
        return s[:m.start() + 1]
    if len(s) <= max_chars:
        return s
    cut = s.rfind(" ", 0, max_chars)
    if cut <= 0:
        cut = max_chars
    return s[:cut].rstrip() + "…"


# Period followed by whitespace and an uppercase letter — treats
# this as a sentence boundary and short-circuits truncation when
# the first sentence already fits the label budget.
import re as _re_label
_SENTENCE_END_RE = _re_label.compile(r"\.\s+[A-Z]")


def _display_name(kind: str, item: dict) -> str | None:
    """Pick the most meaningful display label for an item.

    Resolution order:
      1. ``item['name']`` if non-empty.
      2. ``item['title']`` if non-empty (citations, chapters,
         code_examples).
      3. The kind's text-label field (``summary``, ``claim``,
         ``prompt``, ``text``) truncated to ~80 chars.
      4. ``None`` — caller should treat as "unlabelled" and
         skip rather than silently include.
    """
    if not isinstance(item, dict):
        return None
    for field in ("name", "title"):
        v = item.get(field)
        if isinstance(v, str) and v.strip():
            return v.strip()
    text_field = _KIND_TEXT_LABEL.get(kind)
    if text_field:
        v = item.get(text_field)
        if isinstance(v, str) and v.strip():
            label = _truncate_label(v)
            return label or None
    return None


def _format_field_value(v) -> str:
    """Render a per-item field value as a single Markdown-safe
    string for the report.

    Rules:
      - ``None`` → ``_null_`` so reviewers see the field was
        considered and the source had nothing to fill it with.
      - bool → ``true`` / ``false`` (lowercase, YAML-style).
      - int / float → ``str(v)``.
      - ``str`` → returned verbatim, with internal newlines
        replaced by ``\\n`` escape sequences so the field stays
        on one bullet line. No truncation.
      - list of scalars → comma-joined.
      - list of dicts / dicts → YAML block, indented under the
        bullet so structure is preserved.
      - empty list → ``[]``.
      - anything else → ``str(v)`` as a last resort.
    """
    if v is None:
        return "_null_"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if not v:
            return '""'
        # Collapse internal newlines so the field renders inline.
        # The reviewer can still read the full content; only the
        # whitespace is normalized.
        return v.replace("\r\n", "\n").replace("\n", " \\n ")
    if isinstance(v, list):
        if not v:
            return "[]"
        if all(isinstance(it, (str, int, float, bool)) or it is None
                for it in v):
            return ", ".join(_format_field_value(it) for it in v)
        # Heterogeneous or list-of-dicts: dump as a YAML block. The
        # template indents this under the bullet so it renders as a
        # nested code-style segment.
        return yaml.safe_dump(
            v, sort_keys=False, allow_unicode=True,
            default_flow_style=False,
        ).rstrip()
    if isinstance(v, dict):
        if not v:
            return "{}"
        return yaml.safe_dump(
            v, sort_keys=False, allow_unicode=True,
            default_flow_style=False,
        ).rstrip()
    return str(v)


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
    display label or the kind has no vault-type template.
    """
    name = _display_name(kind, item)
    if not name:
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


# ── prune ───────────────────────────────────────────────


# Wikilink syntax in Obsidian:
#   [[Target]]
#   [[Target|Alias]]      ← we extract Target, ignore Alias
#   [[Target#Heading]]    ← we strip #Heading
#   [[Target^block]]      ← we strip ^block
# We do NOT match [[ ]] inside fenced code blocks (``` ... ```)
# because synthesis hubs may include code samples that contain
# bracketed text by coincidence.
import re as _re

# Match an opening fence line (```lang) and the closing fence (```).
# We toggle a state flag while walking lines.
_FENCE_RE = _re.compile(r"^[\t ]*```")

# Match wikilinks anywhere on a line. We capture the target, which is
# everything before the first '|', '#', or '^'.
_WIKILINK_RE = _re.compile(r"\[\[([^\[\]]+?)\]\]")


def _wikilink_targets(text: str) -> list[str]:
    """Return every wikilink target in ``text``, in encounter order.

    Strips alias (``|...``), heading (``#...``) and block (``^...``)
    suffixes. Skips wikilinks inside fenced code blocks.
    """
    targets: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for raw in _WIKILINK_RE.findall(line):
            # Strip alias (after '|'), heading (after '#'), block
            # (after '^') — keep only the target.
            target = raw
            for sep in ("|", "#", "^"):
                if sep in target:
                    target = target.split(sep, 1)[0]
            target = target.strip()
            if target:
                targets.append(target)
    return targets


def _frontmatter_link_targets(fm: dict) -> list[str]:
    """Wikilink targets that live in the page's YAML frontmatter.

    Synthesis pages list their underlying artifacts under
    ``sources:`` (and sometimes other list-of-wikilinks fields).
    Each entry may already be wrapped in ``[[...]]`` or be a
    plain name; we accept both. Frontmatter wikilinks count
    identically to body wikilinks for prune decisions.
    """
    targets: list[str] = []
    for value in (fm or {}).values():
        if isinstance(value, str):
            inner = value.strip()
            if inner.startswith("[[") and inner.endswith("]]"):
                targets.extend(_wikilink_targets(inner))
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, str):
                    continue
                inner = item.strip()
                if inner.startswith("[[") and inner.endswith("]]"):
                    targets.extend(_wikilink_targets(inner))
                elif inner:
                    targets.append(inner)
    return targets


def _collect_synthesis_link_targets(replica_root: Path) -> list[str]:
    """Walk every synthesis hub page and collect every wikilink
    target the gate operator would click in Obsidian. Order
    preserved (first hub first, body before frontmatter); no
    deduplication — caller normalizes."""
    targets: list[str] = []
    synth_dir = replica_root / SYNTHESIS_DIR
    if not synth_dir.exists():
        return targets
    for entry in sorted(synth_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue
        try:
            raw = entry.read_text(encoding="utf-8")
        except OSError:
            continue
        try:
            fm, body = parse(raw)
        except ValueError:
            fm, body = {}, raw
        targets.extend(_wikilink_targets(body))
        targets.extend(_frontmatter_link_targets(fm))
    return targets


def prune_replica(workdir: Path) -> dict:
    """Prune unreferenced new artifact pages from the replica.

    Walks synthesis hubs, extracts every wikilink target, and
    removes any manifest entry whose name is not linked AND whose
    op is ``create``. Modified entries are always kept (the vault
    already has the page; pruning would delete a vault overwrite
    without removing the underlying page).

    Returns::

        {
          "kept_linked":     [{vault_path, kind, name}, ...],
          "kept_modified":   [{vault_path, kind, name}, ...],
          "pruned":          [{vault_path, kind, name}, ...],
          "orphan_links":    ["Target", ...],
          "manifest_path":   "<replica>/manifest.yaml",
        }

    ``orphan_links`` lists wikilink targets that match neither a
    surviving manifest entry NOR an existing vault page. These
    will render as broken links in Obsidian; the gate operator
    can edit the synthesis hub or accept them.
    """
    rr = _replica_root(workdir)
    if not rr.exists():
        raise FileNotFoundError(f"replica missing at {rr}")
    mp = _manifest_path(workdir)
    if not mp.exists():
        raise FileNotFoundError(f"manifest missing at {mp}")

    manifest = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    entries = list(manifest.get("entries") or [])

    # Build the wikilink target set. Normalize so 'Foo Bar' and
    # 'foo  bar' compare equal.
    raw_targets = _collect_synthesis_link_targets(rr)
    norm_targets = {_normalize(t) for t in raw_targets if t}

    kept_linked: list[dict] = []
    kept_modified: list[dict] = []
    pruned: list[dict] = []
    surviving_entries: list[dict] = []
    surviving_names_norm: set[str] = set()

    for entry in entries:
        name = entry.get("name") or ""
        op   = entry.get("op")
        norm_name = _normalize(name)

        if op == "modified":
            kept_modified.append(_summarize_entry(entry))
            surviving_entries.append(entry)
            surviving_names_norm.add(norm_name)
            continue

        # op == 'create' (or any future op without an existing
        # original) — only keep if synthesis links to it.
        if norm_name in norm_targets:
            kept_linked.append(_summarize_entry(entry))
            surviving_entries.append(entry)
            surviving_names_norm.add(norm_name)
            continue

        # Pruned: delete the replica file and drop the entry.
        vp = entry.get("vault_path")
        if isinstance(vp, str):
            replica_file = rr / vp
            if replica_file.exists():
                try:
                    replica_file.unlink()
                except OSError:
                    pass  # best-effort; manifest removal still happens
        pruned.append(_summarize_entry(entry))

    # Compute orphan links: wikilink targets that match neither
    # a surviving artifact nor an existing vault page.
    seen: set[str] = set()
    orphan_links: list[str] = []
    for raw in raw_targets:
        if not raw:
            continue
        if raw in seen:
            continue
        seen.add(raw)
        norm = _normalize(raw)
        if norm in surviving_names_norm:
            continue
        # Existing vault page check: try the name as a flat
        # filename in any artifact-mode folder. Cheap and
        # sufficient for the orphan signal.
        if _name_matches_any_vault_page(raw):
            continue
        orphan_links.append(raw)

    # Persist the trimmed manifest. Preserve other top-level keys.
    new_manifest = {**manifest, "entries": surviving_entries}
    mp.write_text(
        yaml.safe_dump(new_manifest, sort_keys=False,
                        allow_unicode=True),
        encoding="utf-8",
    )

    return {
        "kept_linked":   kept_linked,
        "kept_modified": kept_modified,
        "pruned":        pruned,
        "orphan_links":  orphan_links,
        "manifest_path": str(mp),
    }


def _summarize_entry(entry: dict) -> dict:
    """Return only the gate-operator-relevant fields of a manifest
    entry, for inclusion in the prune output."""
    return {
        "vault_path": entry.get("vault_path"),
        "kind":       entry.get("kind"),
        "name":       entry.get("name"),
    }


def _name_matches_any_vault_page(name: str) -> bool:
    """True if a vault page exists matching this wikilink target.

    Handles two wikilink shapes Obsidian accepts:

    - **Path-style** — e.g. ``[[10 SOURCES/Articles/Foo]]``. The
      target is a vault-relative path. Check
      ``<VAULT_ROOT>/<target>.md`` directly; do NOT slugify
      (slashes are part of the path, not the filename).
    - **Plain name** — e.g. ``[[Csmith]]``. Search known
      artifact-mode folders for ``<name>.md``. ``10 SOURCES/`` is
      organized one level deep by source kind (``Articles``,
      ``Books``, ``Papers``, ``Videos``), so recurse one level
      there. The other artifact folders are flat.
    """
    from curator.vault.config import VAULT_ROOT

    # Path-style wikilink — exact path lookup, no slug mangling.
    if "/" in name:
        return (VAULT_ROOT / f"{name}.md").exists()

    # Plain name — search flat artifact folders.
    fname = slugify_basename(name) or name
    flat_folders = ("12 KEYWORDS", "13 PEOPLE", "14 MODELS",
                    "11 QUOTES")
    for folder in flat_folders:
        if (VAULT_ROOT / folder / f"{fname}.md").exists():
            return True

    # 10 SOURCES is nested one level by kind; check each
    # subdir for a matching flat filename.
    sources_root = VAULT_ROOT / "10 SOURCES"
    if sources_root.is_dir():
        for sub in sources_root.iterdir():
            if sub.is_dir() and (sub / f"{fname}.md").exists():
                return True

    return False


# ── strip dead links ────────────────────────────────────


# Frontmatter delimiters: keep the original block verbatim so
# unrelated YAML formatting (comments, key order, list style) is
# not perturbed. The body is the only region we rewrite.
_FRONTMATTER_RE = _re.compile(r"\A(---\n.*?\n---\n)(.*)\Z", _re.DOTALL)


def _split_frontmatter_block(raw: str) -> tuple[str, str]:
    """Split the raw text into (frontmatter_block, body).

    ``frontmatter_block`` includes the opening + closing ``---``
    delimiters and the trailing newline so concatenation
    reproduces the original on-disk bytes when body is unchanged.
    Returns ('', raw) when no frontmatter is present.
    """
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return "", raw
    return m.group(1), m.group(2)


def _resolve_visible_text(target: str, alias: str) -> str:
    """Visible text for a stripped wikilink.

    ``[[X|Y]]``         → ``Y`` (alias preserves intent)
    ``[[X]]``           → ``X`` (heading/block dropped)
    ``[[X#anchor]]``    → ``X`` (anchor meaningless without page)
    ``[[X^block]]``     → ``X``
    """
    if alias:
        return alias
    name = target
    for sep in ("#", "^"):
        if sep in name:
            name = name.split(sep, 1)[0]
    return name.strip()


def _replica_page_names(rr: Path) -> set[str]:
    """Normalized stems of every ``.md`` file currently on disk
    in the replica (excluding internal files like manifest /
    report). Reflects post-gate state — files the user deleted
    are absent."""
    names: set[str] = set()
    for path in rr.rglob("*.md"):
        if path.name in _INTERNAL_FILES:
            continue
        names.add(_normalize(path.stem))
    return names


def _strip_body_dead_links(
    body: str,
    replica_names: set[str],
) -> tuple[str, list[dict], int]:
    """Rewrite dead wikilinks in ``body`` to plain text.

    Returns (new_body, stripped, kept):
      stripped — list of {target, replacement} for each dead link
      kept     — count of wikilinks left intact

    Wikilinks inside fenced code blocks are left alone (Obsidian
    does not render them as links there). Intra-page anchor links
    (``[[#section]]``) are kept verbatim.
    """
    stripped: list[dict] = []
    kept = 0
    out_lines: list[str] = []
    in_fence = False

    for line in body.splitlines(keepends=True):
        # Strip the trailing newline only for fence detection;
        # keep the original line unchanged when reassembling.
        bare = line.rstrip("\n")
        if _FENCE_RE.match(bare):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence:
            out_lines.append(line)
            continue

        def _sub(match: "_re.Match[str]") -> str:
            nonlocal kept
            inner = match.group(1)
            target_part, sep, alias = inner.partition("|")
            target_part = target_part.strip()
            alias = alias.strip()

            # Intra-page anchor — no target page to resolve.
            if target_part.startswith("#"):
                kept += 1
                return match.group(0)

            # Strip heading/block from target before resolution.
            page_target = target_part
            for s in ("#", "^"):
                if s in page_target:
                    page_target = page_target.split(s, 1)[0]
            page_target = page_target.strip()

            # Path-style or plain — both flow through
            # _name_matches_any_vault_page; replica names cover
            # the workdir side.
            norm = _normalize(page_target)
            if norm in replica_names:
                kept += 1
                return match.group(0)
            if _name_matches_any_vault_page(page_target):
                kept += 1
                return match.group(0)

            replacement = _resolve_visible_text(target_part, alias)
            stripped.append({
                "target":      inner,
                "replacement": replacement,
            })
            return replacement

        new_line = _WIKILINK_RE.sub(_sub, line)
        out_lines.append(new_line)

    return "".join(out_lines), stripped, kept


def strip_dead_links(workdir: Path) -> dict:
    """Rewrite synthesis hub wikilinks whose target won't resolve
    at apply time.

    Runs AFTER the human gate and BEFORE apply-replica. The user
    may have deleted replica files at the gate; references to
    those deletions become dead ``[[wikilinks]]`` that Obsidian
    paints as broken. This step rewrites them to plain text:

    - ``[[Target]]``         → ``Target``
    - ``[[Target|Alias]]``   → ``Alias``
    - ``[[Target#anchor]]``  → ``Target``
    - ``[[#anchor]]``        → kept verbatim (intra-page link)

    A target resolves if either:

    - a ``.md`` file is present in the post-gate replica (any
      depth, excluding internal files), OR
    - an existing vault page matches via
      ``_name_matches_any_vault_page``.

    Only synthesis hubs (``21 WIKI/*.md``) are rewritten. Atomic
    pages are leaves and don't carry cross-references. Wikilinks
    in fenced code blocks are NOT rewritten. Frontmatter is left
    verbatim — its ``sources:`` entries are metadata, not
    rendered links.

    Returns::

        {
          "files_edited":   [{path, stripped: [...]}, ...],
          "stripped_total": int,
          "kept_total":     int,
        }
    """
    rr = _replica_root(workdir)
    if not rr.exists():
        raise FileNotFoundError(f"replica missing at {rr}")

    synth_dir = rr / SYNTHESIS_DIR
    if not synth_dir.exists():
        return {
            "files_edited":   [],
            "stripped_total": 0,
            "kept_total":     0,
        }

    replica_names = _replica_page_names(rr)

    files_edited: list[dict] = []
    stripped_total = 0
    kept_total = 0

    for entry in sorted(synth_dir.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue
        try:
            raw = entry.read_text(encoding="utf-8")
        except OSError:
            continue

        fm_block, body = _split_frontmatter_block(raw)
        new_body, stripped, kept = _strip_body_dead_links(
            body, replica_names)
        kept_total += kept
        if not stripped:
            continue
        stripped_total += len(stripped)
        new_text = fm_block + new_body
        entry.write_text(new_text, encoding="utf-8")
        files_edited.append({
            "path":     str(entry),
            "stripped": stripped,
        })

    return {
        "files_edited":   files_edited,
        "stripped_total": stripped_total,
        "kept_total":     kept_total,
    }


# ── report ──────────────────────────────────────────────


def build_report(workdir: Path) -> dict:
    """Render the gate operator's overview ``_REPORT.md`` into the
    replica root.

    Reads upstream task outputs directly:
    - classify's quintet + topic
    - extract-summary's summary text (pasted verbatim)
    - each ``extract-<kind>``'s items (kind name + count + names)
    - the synthesis task's emitted paths
    - the manifest (post-prune) to compute materialised/skipped
      per artifact-mode kind
    - prune-replica's output (orphan synthesis links)

    Writes to ``<wd>/vault-replica/_REPORT.md``. Listed in
    ``_INTERNAL_FILES`` so apply-replica skips it.
    """
    from engine import store
    from curator import quintet as q_mod
    plan = store.load_plan(workdir)

    classify = _safe_load(workdir, "classify", plan)
    quintet  = (classify or {}).get("quintet") or {}
    topic    = (classify or {}).get("topic") or "(untyped)"

    summary_doc = _safe_load(workdir, "extract-summary", plan)
    summary = ((summary_doc or {}).get("summary") or "").strip()

    # Per-kind extractor outputs (everything except summary).
    # Each kind becomes a section in the report; each item
    # becomes a sub-section with its full field set rendered as
    # a bullet list. No truncation — the report is the
    # gate operator's authoritative dump.
    raw_extractions: dict[str, list[dict]] = {}
    for task in plan.tasks:
        if not task.id.startswith("extract-"):
            continue
        kind = task.id[len("extract-"):]
        if kind == "summary":
            continue
        out = _safe_load(workdir, task.id, plan) or {}
        items = out.get(kind)
        if not isinstance(items, list):
            continue
        kept: list[dict] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            label = _display_name(kind, it)
            if not label:
                continue
            kept.append({"_display_name": label, "_raw": it})
        raw_extractions[kind] = kept

    # Manifest (post-prune) tells us which items actually got
    # built as atomic pages. Items present in extractor output
    # but absent from the manifest are "(not materialized)".
    # Synthesis-mode kinds are always not materialized — they
    # have no atomic-page form by design.
    manifest = _load_manifest(workdir) or {}
    manifest_entries = manifest.get("entries") or []
    materialised_by_kind: dict[str, set[str]] = {}
    for entry in manifest_entries:
        kind = entry.get("kind")
        name = entry.get("name")
        if not isinstance(kind, str) or not isinstance(name, str):
            continue
        materialised_by_kind.setdefault(kind, set()).add(_normalize(name))

    # Build the per-kind / per-item structure passed to the
    # template. Order kinds alphabetically for stable output.
    extractions: dict[str, dict] = {}
    for kind in sorted(raw_extractions.keys()):
        items = raw_extractions[kind]
        mat_norms = materialised_by_kind.get(kind, set())
        rendered_items: list[dict] = []
        for entry in items:
            label = entry["_display_name"]
            raw = entry["_raw"]
            # Field list: every key on the item except internal
            # placeholders the report doesn't need to surface.
            fields: list[dict] = []
            for k, v in raw.items():
                if k == "_schema":
                    continue
                fields.append({
                    "name":  k,
                    "value": _format_field_value(v),
                })
            rendered_items.append({
                "display_name": label,
                "materialized": _normalize(label) in mat_norms,
                "fields":       fields,
            })
        extractions[kind] = {"items": rendered_items}

    synthesis_doc = _safe_load(workdir, "synthesis", plan)
    synthesis_paths = ((synthesis_doc or {}).get("paths") or [])

    # Orphan synthesis links — populated by prune-replica's output.
    prune_doc = _safe_load(workdir, "prune-replica", plan) or {}
    orphan_links = prune_doc.get("orphan_links") or []
    if not isinstance(orphan_links, list):
        orphan_links = []

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
    for entry in manifest_entries:
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
        extractions,
        synthesis_paths, orphan_links,
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
    extractions: dict[str, dict],
    synthesis_paths: list[str],
    orphan_links: list[str],
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
        "synthesis_paths":       synthesis_paths,
        "orphan_links":          orphan_links,
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
    # Synthesis pages (under ``21 WIKI/``) are expected here:
    # the synthesis agent writes them directly via fs_write rather
    # than going through the build-replica manifest. Validate +
    # apply them just like tracked entries; vault-state decides
    # ``op`` (create vs modified).
    #
    # Untracked files OUTSIDE ``21 WIKI/`` are flagged as
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

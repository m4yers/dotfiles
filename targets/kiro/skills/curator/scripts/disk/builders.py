"""Per-item JSON builders.

Agents do not write raw JSON. For every canonical JSON file in the
pipeline there is a matching set of builder functions — ``*-init``
creates an empty shell, ``*-add`` / ``*-set-*`` mutate it — exposed
as CLI subcommands via ``__main__.py``.

Every mutation goes through ``_update_json_file``: read current
file (or init shell), apply mutation, validate against the schema,
write atomically. The canonical file therefore contains only
schema-valid content at every observable moment, regardless of how
many tool calls built it.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Iterable

import jsonschema

# Schemas consulted by ``_write_json`` live next to this module. Every
# canonical JSON artifact mutated by builders is validated against its
# schema before being written atomically to disk.
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


def _write_json(path: str | Path, data: Any, schema_name: str) -> dict:
    """Atomic schema-gated JSON write.

    Validates ``data`` against ``<SCHEMA_DIR>/<schema_name>``, writes
    ``<path>.tmp`` with the serialized form, then ``os.replace``s
    over ``path``. A crash or schema failure mid-write never leaves
    a partial canonical file.
    """
    schema = json.loads((SCHEMA_DIR / schema_name).read_text())
    jsonschema.validate(instance=data, schema=schema)
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    os.replace(tmp, dest)
    return {"ok": True, "path": str(dest)}


# ── core helper ──────────────────────────────────────────

def _update_json_file(
    path: Path,
    schema_name: str,
    mutate: Callable[[dict], None],
    init: Callable[[], dict],
) -> dict:
    """Read file (or init), mutate in place, schema-validate, write.

    ``mutate`` is called with the current dict and must modify it in
    place. ``init`` returns the starting dict when the file does not
    yet exist. Returns ``{ok: True, path: str}`` on success; raises
    ``jsonschema.ValidationError`` on schema failure (_write_json
    is the write gate, so nothing lands on disk if the schema fails).
    """
    if path.exists():
        data = json.loads(path.read_text())
    else:
        data = init()
    mutate(data)
    _write_json(path, data, schema_name)
    return {"ok": True, "path": str(path)}


def _read_text_or_none(arg_value: str | None, file_arg: str | None) -> str | None:
    """Return ``arg_value`` verbatim, or the contents of ``file_arg``.

    Callers pass paired ``--foo`` / ``--foo-file`` flags so agents can
    supply short strings inline and multi-line content via a file.
    Exactly one must be supplied or neither (optional fields).
    """
    if arg_value is not None and file_arg is not None:
        raise ValueError("supply either inline value or file, not both")
    if file_arg is not None:
        return Path(file_arg).read_text(encoding="utf-8").rstrip("\n")
    return arg_value


def _read_text_required(arg_value: str | None, file_arg: str | None,
                        field: str) -> str:
    v = _read_text_or_none(arg_value, file_arg)
    if v is None:
        raise ValueError(f"{field} required")
    return v


# ── summary.json ─────────────────────────────────────────

def summary_emit(workdir: str, summary_file: str,
                 claims: Iterable[str]) -> dict:
    """Write summary.json in one shot.

    Summary has only two fields (summary + key_claims). No per-item
    append needed; the agent calls this once with all claims inline.
    """
    path = Path(workdir) / "summary.json"
    data = {
        "summary": Path(summary_file).read_text(encoding="utf-8").strip(),
        "key_claims": list(claims),
    }
    _write_json(path, data, "summary.schema.json")
    return {"ok": True, "path": str(path)}


# ── sources.json ─────────────────────────────────────────

def sources_init(workdir: str) -> dict:
    path = Path(workdir) / "sources.json"
    _write_json(path, {"referenced": []}, "sources.schema.json")
    return {"ok": True, "path": str(path)}


def source_add(
    workdir: str,
    id_: str,
    type_: str,
    mention_context: str,
    *,
    title: str | None = None,
    authors: list[str] | None = None,
    year: int | None = None,
    arxiv: str | None = None,
    doi: str | None = None,
    isbn: str | None = None,
    url: str | None = None,
) -> dict:
    path = Path(workdir) / "sources.json"

    entry: dict[str, Any] = {
        "id": id_,
        "type": type_,
        "mention_context": mention_context,
    }
    if title is not None:
        entry["title"] = title
    if authors:
        entry["authors"] = authors
    if year is not None:
        entry["year"] = year
    for k, v in (("arxiv", arxiv), ("doi", doi), ("isbn", isbn), ("url", url)):
        if v is not None:
            entry[k] = v

    def mutate(data: dict) -> None:
        data.setdefault("referenced", []).append(entry)

    return _update_json_file(
        path, "sources.schema.json", mutate,
        init=lambda: {"referenced": []},
    )


# ── items.json (keywords / people / models) ──────────────

_ITEM_KIND_TO_FILE = {
    "keyword": "keywords.json",
    "person":  "people.json",
    "model":   "models.json",
}


def items_init(workdir: str, kind: str) -> dict:
    filename = _ITEM_KIND_TO_FILE.get(kind)
    if not filename:
        raise ValueError(f"unknown kind: {kind}")
    path = Path(workdir) / filename
    _write_json(path, {"items": []}, "items.schema.json")
    return {"ok": True, "path": str(path)}


def item_add(
    workdir: str,
    kind: str,
    *,
    id_: str,
    name: str,
    action: str,
    rationale: str,
    match_existing: str | None = None,
    body_file: str | None = None,
    frontmatter_file: str | None = None,
    proposed_section: str | None = None,
    proposed_mode: str | None = None,
    frontmatter_delta_file: str | None = None,
) -> dict:
    filename = _ITEM_KIND_TO_FILE.get(kind)
    if not filename:
        raise ValueError(f"unknown kind: {kind}")
    path = Path(workdir) / filename

    import yaml

    entry: dict[str, Any] = {
        "id": id_,
        "name": name,
        "action": action,
        "rationale": rationale,
        "match_existing": match_existing,
    }

    if action == "create":
        if frontmatter_file is None:
            raise ValueError("action=create requires --frontmatter-file")
        if body_file is None:
            raise ValueError("action=create requires --body-file")
        entry["proposed_frontmatter"] = yaml.safe_load(
            Path(frontmatter_file).read_text()) or {}
        entry["proposed_body"] = Path(body_file).read_text(encoding="utf-8")
    elif action == "extend":
        if proposed_section is None or proposed_mode is None or body_file is None:
            raise ValueError("action=extend requires --body-file, "
                             "--proposed-section, --proposed-mode")
        entry["proposed_section"] = proposed_section
        entry["proposed_mode"] = proposed_mode
        entry["proposed_body"] = Path(body_file).read_text(encoding="utf-8")
        if frontmatter_delta_file is not None:
            entry["proposed_frontmatter_delta"] = yaml.safe_load(
                Path(frontmatter_delta_file).read_text()) or {}
    else:
        raise ValueError(f"action must be create|extend, got {action!r}")

    def mutate(data: dict) -> None:
        data.setdefault("items", []).append(entry)

    return _update_json_file(
        path, "items.schema.json", mutate,
        init=lambda: {"items": []},
    )


# ── verdicts/<kind>-attempt-<N>.json ─────────────────────

def _verdict_path(workdir: str, kind: str, attempt: int) -> Path:
    return Path(workdir) / "verdicts" / f"{kind}-attempt-{attempt}.json"


def _verdict_init_shell(kind: str, attempt: int) -> dict:
    return {
        "kind":     kind,
        "attempts": attempt,
        "verdicts": [],
        "meta":     {"items_total": 0, "accept": 0, "review": 0, "reject": 0},
    }


def _recount_verdict_meta(data: dict) -> None:
    vs = data.get("verdicts", [])
    data["meta"] = {
        "items_total": len(vs),
        "accept":      sum(1 for v in vs if v["verdict"] == "ACCEPT"),
        "review":      sum(1 for v in vs if v["verdict"] == "REVIEW"),
        "reject":      sum(1 for v in vs if v["verdict"] == "REJECT"),
    }


def verdict_init(workdir: str, kind: str, attempt: int) -> dict:
    path = _verdict_path(workdir, kind, attempt)
    _write_json(path, _verdict_init_shell(kind, attempt),
                   "verdict.schema.json")
    return {"ok": True, "path": str(path)}


def verdict_add(
    workdir: str,
    kind: str,
    attempt: int,
    *,
    id_: str,
    verdict: str,
    rewrite_suggestion: str | None = None,
) -> dict:
    path = _verdict_path(workdir, kind, attempt)

    entry: dict[str, Any] = {"id": id_, "verdict": verdict, "issues": []}
    if rewrite_suggestion is not None:
        entry["rewrite_suggestion"] = rewrite_suggestion

    def mutate(data: dict) -> None:
        # Reject duplicate id — that would corrupt the verdict set.
        if any(v["id"] == id_ for v in data.get("verdicts", [])):
            raise ValueError(f"verdict id already present: {id_}")
        data.setdefault("verdicts", []).append(entry)
        _recount_verdict_meta(data)

    return _update_json_file(
        path, "verdict.schema.json", mutate,
        init=lambda: _verdict_init_shell(kind, attempt),
    )


def verdict_add_issue(
    workdir: str,
    kind: str,
    attempt: int,
    *,
    id_: str,
    severity: str,
    category: str,
    message: str,
    location: str | None = None,
    source_evidence: str | None = None,
) -> dict:
    path = _verdict_path(workdir, kind, attempt)

    issue: dict[str, Any] = {
        "severity": severity,
        "category": category,
        "message":  message,
    }
    if location is not None:
        issue["location"] = location
    if source_evidence is not None:
        issue["source_evidence"] = source_evidence

    def mutate(data: dict) -> None:
        for v in data.get("verdicts", []):
            if v["id"] == id_:
                v.setdefault("issues", []).append(issue)
                return
        raise ValueError(f"no verdict with id {id_!r}; "
                         f"call verdict-add first")

    return _update_json_file(
        path, "verdict.schema.json", mutate,
        init=lambda: _verdict_init_shell(kind, attempt),
    )


# ── composed.json ────────────────────────────────────────

def _composed_path(workdir: str) -> Path:
    return Path(workdir) / "composed.json"


def _composed_init_shell() -> dict:
    return {
        "source":          {"path": "", "basename": "", "type": "unknown"},
        "summary":         "",
        "proposals": {
            "keywords":  [],
            "people":    [],
            "models":    [],
            "synthesis": [],
        },
        "related_sources": [],
    }


def composed_init(workdir: str, source_path: str, source_type: str,
                  source_basename: str) -> dict:
    path = _composed_path(workdir)
    data = _composed_init_shell()
    data["source"] = {
        "path":     source_path,
        "basename": source_basename,
        "type":     source_type,
    }
    # summary must be non-empty per schema; set a placeholder that the
    # agent overwrites with composed-set-summary before any consumer
    # reads the file.
    data["summary"] = "PENDING"
    _write_json(path, data, "composed.schema.json")
    return {"ok": True, "path": str(path)}


def composed_set_summary(workdir: str, summary_file: str) -> dict:
    path = _composed_path(workdir)
    summary = Path(summary_file).read_text(encoding="utf-8").strip()
    if not summary:
        raise ValueError("summary is empty")

    def mutate(data: dict) -> None:
        data["summary"] = summary

    return _update_json_file(
        path, "composed.schema.json", mutate,
        init=_composed_init_shell,
    )


def _composed_add_item(
    workdir: str, bucket: str,
    *,
    id_: str, name: str, action: str, rationale: str,
    match_existing: str | None,
    body_file: str, frontmatter_file: str,
) -> dict:
    path = _composed_path(workdir)
    import yaml
    entry: dict[str, Any] = {
        "id": id_,
        "name": name,
        "action": action,
        "rationale": rationale,
        "match_existing": match_existing,
        "proposed_frontmatter": yaml.safe_load(
            Path(frontmatter_file).read_text()) or {},
        "proposed_body": Path(body_file).read_text(encoding="utf-8"),
    }

    def mutate(data: dict) -> None:
        data.setdefault("proposals", {}).setdefault(bucket, []).append(entry)

    return _update_json_file(
        path, "composed.schema.json", mutate,
        init=_composed_init_shell,
    )


_COMPOSED_ENTITY_KIND_TO_BUCKET = {
    "keyword": "keywords",
    "person":  "people",
    "model":   "models",
}


def composed_add_entity(
    workdir: str, kind: str, **kw,
) -> dict:
    """Append a reconciled keyword/person/model to composed.json.

    Thin dispatch over ``_composed_add_item`` — kind maps 1:1 to the
    bucket name inside ``composed.proposals``. Synthesis pages use
    ``composed_add_synthesis`` because they carry ``path`` instead of
    ``name`` and have no ``match_existing``.
    """
    bucket = _COMPOSED_ENTITY_KIND_TO_BUCKET.get(kind)
    if bucket is None:
        raise ValueError(
            f"unknown entity kind: {kind!r} "
            f"(expected one of {sorted(_COMPOSED_ENTITY_KIND_TO_BUCKET)})"
        )
    return _composed_add_item(workdir, bucket, **kw)


def composed_add_synthesis(
    workdir: str, *,
    id_: str, path_: str, action: str, rationale: str,
    body_file: str, frontmatter_file: str,
) -> dict:
    import yaml
    path = _composed_path(workdir)
    entry: dict[str, Any] = {
        "id": id_,
        "path": path_,
        "action": action,
        "rationale": rationale,
        "proposed_frontmatter": yaml.safe_load(
            Path(frontmatter_file).read_text()) or {},
        "proposed_body": Path(body_file).read_text(encoding="utf-8"),
    }

    def mutate(data: dict) -> None:
        data.setdefault("proposals", {}).setdefault("synthesis", []).append(entry)

    return _update_json_file(
        path, "composed.schema.json", mutate,
        init=_composed_init_shell,
    )


def composed_add_related_source(
    workdir: str, *,
    type_: str, title: str, reason: str,
    authors: list[str] | None = None,
    year: int | None = None,
    arxiv: str | None = None, doi: str | None = None,
    isbn: str | None = None, url: str | None = None,
) -> dict:
    path = _composed_path(workdir)
    entry: dict[str, Any] = {"type": type_, "title": title, "reason": reason}
    if authors:
        entry["authors"] = authors
    if year is not None:
        entry["year"] = year
    for k, v in (("arxiv", arxiv), ("doi", doi), ("isbn", isbn), ("url", url)):
        if v is not None:
            entry[k] = v

    def mutate(data: dict) -> None:
        data.setdefault("related_sources", []).append(entry)

    return _update_json_file(
        path, "composed.schema.json", mutate,
        init=_composed_init_shell,
    )


_KIND_TO_BUCKET: dict[str, str | None] = {
    # Each extractor's judge verdicts map to one bucket in composed.json.
    # summary has no per-item surface to attach issues to, so the summary
    # kind's verdicts are intentionally ignored here.
    "summary":  None,
    "sources":  "related_sources",
    "keywords": "keywords",
    "people":   "people",
    "models":   "models",
}


def compose_merge_issues(workdir: str) -> dict:
    """Copy REVIEW-verdict issues from verdicts/<kind>.json onto
    composed.json items by id. Idempotent: the issues array on each
    paired item is replaced with the authoritative verdict issue list
    on every call, so repeating the command does not duplicate issues.

    Synthesis proposals have no paired verdict (composer-invented);
    they keep whatever issues array they already have.

    For keywords/people/models, a verdict id with no matching item in
    composed.json is a composer contract violation and raises.

    For related_sources, unmatched ids are silently skipped because the
    composer filters the sources kind's output (≤ 10 follow-ups, drop
    vault-present entries) — a verdict id absent from related_sources
    simply means the composer chose not to recommend that source.
    """
    composed_path = _composed_path(workdir)
    if not composed_path.exists():
        raise FileNotFoundError(
            f"composed.json not found under {workdir!r}; run composer first")
    verdicts_dir = Path(workdir) / "verdicts"

    def mutate(data: dict) -> None:
        for kind, bucket in _KIND_TO_BUCKET.items():
            if bucket is None:
                continue
            verdict_file = verdicts_dir / f"{kind}.json"
            if not verdict_file.exists():
                continue
            verdict_data = json.loads(verdict_file.read_text())

            if bucket == "related_sources":
                targets = data.get("related_sources", [])
            else:
                targets = data.get("proposals", {}).get(bucket, [])
            targets_by_id = {
                t["id"]: t for t in targets if t.get("id") is not None
            }

            # Reset issue arrays for ids the verdict file covers; a
            # repeated call must not duplicate issues.
            for v in verdict_data.get("verdicts", []):
                vid = v.get("id")
                if vid not in targets_by_id:
                    if bucket == "related_sources":
                        # Composer may have filtered this source out.
                        continue
                    raise ValueError(
                        f"{kind} verdict id {vid!r} has no matching item "
                        f"in composed.json {bucket!r}"
                    )
                target = targets_by_id[vid]
                if v.get("verdict") == "REVIEW" and v.get("issues"):
                    target["issues"] = list(v["issues"])
                else:
                    target.pop("issues", None)

    return _update_json_file(
        composed_path, "composed.schema.json", mutate,
        init=_composed_init_shell,
    )


# ── approved.json ────────────────────────────────────────

def _approved_path(workdir: str) -> Path:
    return Path(workdir) / "approved.json"


def approved_init(workdir: str) -> dict:
    path = _approved_path(workdir)
    _write_json(path,
                   {"workdir": str(Path(workdir).resolve()), "decisions": []},
                   "approved.schema.json")
    return {"ok": True, "path": str(path)}


def approved_add_decision(
    workdir: str, *,
    id_: str, action: str,
    override_body_file: str | None = None,
    override_frontmatter_file: str | None = None,
    override_path: str | None = None,
    override_section: str | None = None,
    override_mode: str | None = None,
    new_name: str | None = None,
) -> dict:
    import yaml
    path = _approved_path(workdir)
    entry: dict[str, Any] = {"id": id_, "action": action}

    if action not in ("approve", "edit", "deny", "rename", "redirect"):
        raise ValueError(f"invalid action: {action}")

    if override_body_file is not None:
        entry["override_body"] = Path(override_body_file).read_text(encoding="utf-8")
    if override_frontmatter_file is not None:
        entry["override_frontmatter"] = yaml.safe_load(
            Path(override_frontmatter_file).read_text()) or {}
    if override_path is not None:
        entry["override_path"] = override_path
    if override_section is not None:
        entry["override_section"] = override_section
    if override_mode is not None:
        entry["override_mode"] = override_mode
    if new_name is not None:
        entry["new_name"] = new_name

    def mutate(data: dict) -> None:
        data.setdefault("decisions", []).append(entry)

    return _update_json_file(
        path, "approved.schema.json", mutate,
        init=lambda: {"workdir": str(Path(workdir).resolve()), "decisions": []},
    )

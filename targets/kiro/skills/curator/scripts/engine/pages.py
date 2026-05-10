"""Page CRUD — write, extend, read, stubs, orphans, verify-batch, materialize."""
from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

import yaml

from engine import vault
from engine.config import STUB_BODY_MIN


# ── write ──────────────────────────────────────────────

def write(
    vault_path: str,
    body_file: str,
    frontmatter_file: str,
    allow_uncited: bool = False,
) -> dict:
    """Create or overwrite a page. Enforces scope and citation rules."""
    vault.require_writable(vault_path)

    body = Path(body_file).read_text(encoding="utf-8")
    fm_raw = Path(frontmatter_file).read_text(encoding="utf-8")
    fm = yaml.safe_load(fm_raw) or {}
    if not isinstance(fm, dict):
        raise ValueError("frontmatter must be a yaml mapping")

    _ensure_required_frontmatter(fm)
    if not allow_uncited:
        _ensure_cited(fm, body)

    fm.setdefault("last_updated", datetime.date.today().isoformat())

    existed = vault.abs_path(vault_path).exists()
    vault.save(vault_path, fm, body)
    return {
        "ok": True,
        "path": vault_path,
        "action": "overwrote" if existed else "created",
        "bytes": vault.abs_path(vault_path).stat().st_size,
    }


# ── extend ─────────────────────────────────────────────

def extend(
    vault_path: str,
    section: str,
    body_file: str,
    mode: str = "append",
    frontmatter_delta_file: str | None = None,
) -> dict:
    """Append or replace a section in an existing page."""
    vault.require_writable(vault_path)
    page = vault.load(vault_path)

    added_body = Path(body_file).read_text(encoding="utf-8").rstrip() + "\n"
    new_body = _apply_section(page.body, section, added_body, mode)

    new_fm = dict(page.frontmatter)
    if frontmatter_delta_file:
        delta = yaml.safe_load(Path(frontmatter_delta_file).read_text())
        if not isinstance(delta, dict):
            raise ValueError("frontmatter delta must be a mapping")
        _apply_frontmatter_delta(new_fm, delta)

    new_fm["last_updated"] = datetime.date.today().isoformat()

    _ensure_required_frontmatter(new_fm)
    _ensure_cited(new_fm, new_body)

    vault.save(vault_path, new_fm, new_body)
    return {
        "ok": True,
        "path": vault_path,
        "action": f"extended({mode})",
        "section": section,
        "bytes": vault.abs_path(vault_path).stat().st_size,
    }


_SECTION_RE_TMPL = r"(^|\n)##\s+{title}\s*\n"


def _apply_section(body: str, section: str, added: str, mode: str) -> str:
    title_pat = re.escape(section)
    rx = re.compile(_SECTION_RE_TMPL.format(title=title_pat))
    m = rx.search(body)
    header = f"## {section}\n"

    if not m:
        # Section not present — append with header.
        sep = "" if body.endswith("\n") else "\n"
        return body + sep + "\n" + header + added

    start = m.end()
    # Find end of section (next `## ` header or EOF).
    nxt = re.search(r"\n##\s+[^\n]+\n", body[start:])
    end = start + nxt.start() if nxt else len(body)
    section_body = body[start:end].strip("\n")

    if mode == "replace":
        new_section = added.rstrip() + "\n"
    else:
        sep = "\n\n" if section_body else ""
        new_section = section_body + sep + added
        if not new_section.endswith("\n"):
            new_section += "\n"

    return body[: start] + new_section + body[end:]


def _apply_frontmatter_delta(fm: dict, delta: dict):
    """Merge keys from delta. Special handling for `sources_add` which unions."""
    for k, v in delta.items():
        if k == "sources_add":
            existing = fm.get("sources") or []
            fm["sources"] = sorted(set(existing) | set(v))
        elif k == "aliases_add":
            existing = fm.get("aliases") or []
            fm["aliases"] = sorted(set(existing) | set(v))
        elif k == "covers_add":
            existing = fm.get("covers") or []
            fm["covers"] = sorted(set(existing) | set(v))
        else:
            fm[k] = v


# ── read ───────────────────────────────────────────────

def read(vault_path: str, section: str | None = None) -> dict:
    page = vault.load(vault_path)
    if section is None:
        return {
            "path": vault_path,
            "frontmatter": page.frontmatter,
            "body": page.body,
        }
    title_pat = re.escape(section)
    rx = re.compile(_SECTION_RE_TMPL.format(title=title_pat))
    m = rx.search(page.body)
    if not m:
        return {"path": vault_path, "section": section, "body": None}
    start = m.end()
    nxt = re.search(r"\n##\s+[^\n]+\n", page.body[start:])
    end = start + nxt.start() if nxt else len(page.body)
    return {
        "path": vault_path,
        "section": section,
        "body": page.body[start:end].strip(),
    }


# ── stubs ──────────────────────────────────────────────

def stubs(folder: str | None = None) -> dict:
    """List pages that are empty or frontmatter-only.

    A stub = file body (after frontmatter) has <50 characters of
    non-whitespace content.
    """
    if folder:
        paths = vault.list_md(folder)
    else:
        paths = [p for p in vault.iter_all_md()]
    out = []
    for p in paths:
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            continue
        _, body = vault.try_parse(raw)
        if len(body.strip()) < STUB_BODY_MIN:
            out.append({"path": vault.rel_path(p), "size": p.stat().st_size})
    return {"stubs": sorted(out, key=lambda x: x["path"])}


# ── orphans ────────────────────────────────────────────

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def orphans() -> dict:
    """Pages (in writable folders) that no other page links to."""
    all_paths = vault.iter_all_md()
    link_targets: set[str] = set()
    for p in all_paths:
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in _WIKILINK_RE.finditer(raw):
            target = m.group(1).strip()
            # Wikilinks can be by basename or by vault-relative path.
            link_targets.add(target)
            link_targets.add(Path(target).stem)

    out = []
    for p in all_paths:
        vp = vault.rel_path(p)
        if not _is_writable_folder(vp):
            continue
        if p.stem in link_targets or vp.removesuffix(".md") in link_targets:
            continue
        out.append(vp)
    return {"orphans": sorted(out)}


def _is_writable_folder(vault_path: str) -> bool:
    for d in (vault.KEYWORDS_DIR, vault.PEOPLE_DIR, vault.MODELS_DIR, vault.SYNTHESIS_DIR):
        if vault_path.startswith(d + "/"):
            return True
    return False


# ── verify-batch ───────────────────────────────────────

def verify_batch(approved_json_path: str, composed_json_path: str | None = None) -> dict:
    """Check every approved decision's target file exists on disk.

    approved.json carries only ids + overrides. The canonical target
    path for each id lives in composed.json, so we join on id to
    resolve the path before checking existence.
    """
    approved = json.loads(Path(approved_json_path).read_text())

    if composed_json_path is None:
        # Default: sibling composed.json in the same workdir.
        composed_json_path = str(Path(approved_json_path).parent / "composed.json")
    composed = json.loads(Path(composed_json_path).read_text())

    # Build id → composed path map across every proposal section.
    id_to_path: dict[str, str] = {}
    for bucket in ("keywords", "people", "models", "synthesis"):
        for item in composed.get("proposals", {}).get(bucket, []) or []:
            iid = item.get("id")
            path = item.get("path") or item.get("match_existing")
            if iid and path:
                id_to_path[iid] = path

    missing = []
    for d in approved.get("decisions", []):
        if d.get("action") == "deny":
            continue
        iid = d.get("id")
        target = d.get("override_path") or id_to_path.get(iid)
        if not target:
            missing.append({"id": iid, "reason": "no path resolved from approved+composed"})
            continue
        if not vault.abs_path(target).exists():
            missing.append({"id": iid, "path": target})
    return {"ok": len(missing) == 0, "missing": missing}


# ── frontmatter / citation helpers ─────────────────────

_REQUIRED_FIELDS = ("type",)


def _ensure_required_frontmatter(fm: dict):
    for f in _REQUIRED_FIELDS:
        if f not in fm:
            raise ValueError(f"frontmatter missing required field: {f}")


def _ensure_cited(fm: dict, body: str):
    """Require sources frontmatter OR a wikilink into 10 SOURCES/ or 11 QUOTES/ in body."""
    sources = fm.get("sources") or []
    if sources:
        return
    # Check body for a source-pointing wikilink.
    for m in _WIKILINK_RE.finditer(body):
        t = m.group(1).strip()
        if t.startswith((vault.SOURCES_DIR, vault.QUOTES_DIR)):
            return
    raise ValueError(
        "page has no sources frontmatter and no citation wikilink; "
        "pass --allow-uncited only for stubs"
    )


# ── materialize ────────────────────────────────────────

def materialize(approved_json_path: str, composed_json_path: str | None = None) -> dict:
    """Expand approved proposals into body + frontmatter files in the workdir.

    Reads composed.json for the canonical proposed_body / proposed_frontmatter
    (or proposed_section / proposed_mode for extends) and approved.json for
    user decisions (approve / edit / deny / rename / redirect with overrides).

    Writes one pair of files per approved item into the workdir:
        <id>.body.md
        <id>.fm.yml       (create-style items)
        <id>.fmdelta.yml  (extend-style items)

    Returns a plan array telling the orchestrator exactly which
    `page write` / `page extend` calls to make, with resolved paths.
    """
    approved_path = Path(approved_json_path)
    workdir = approved_path.parent
    if composed_json_path is None:
        composed_json_path = str(workdir / "composed.json")

    approved = json.loads(approved_path.read_text())
    composed = json.loads(Path(composed_json_path).read_text())

    # Flatten composed proposals into an id-keyed map.
    items: dict[str, dict] = {}
    for bucket in ("keywords", "people", "models", "synthesis"):
        for it in composed.get("proposals", {}).get(bucket, []) or []:
            if "id" in it:
                items[it["id"]] = dict(it, _bucket=bucket)

    plan = []
    for d in approved.get("decisions", []):
        iid = d.get("id")
        action = d.get("action", "approve")
        if action == "deny":
            plan.append({"id": iid, "skip": True, "reason": "denied"})
            continue

        item = items.get(iid)
        if item is None:
            plan.append({"id": iid, "skip": True, "reason": "id not in composed.json"})
            continue

        # Resolve the target path. Priority: override_path > rename (derived) > item.path > match_existing.
        target = (
            d.get("override_path")
            or _rename_to_path(item, d.get("new_name"))
            or item.get("path")
            or item.get("match_existing")
        )
        if not target:
            plan.append({"id": iid, "skip": True, "reason": "no target path"})
            continue

        op = "extend" if item.get("action") == "extend" else "write"
        body = d.get("override_body") or item.get("proposed_body") or ""
        body_path = workdir / f"{iid}.body.md"
        body_path.write_text(body, encoding="utf-8")

        entry = {"id": iid, "op": op, "target": target, "body_file": str(body_path)}

        if op == "write":
            fm = d.get("override_frontmatter") or item.get("proposed_frontmatter") or {}
            fm_path = workdir / f"{iid}.fm.yml"
            fm_path.write_text(yaml.safe_dump(fm, sort_keys=False, allow_unicode=True), encoding="utf-8")
            entry["frontmatter_file"] = str(fm_path)
        else:
            entry["section"] = d.get("override_section") or item.get("proposed_section") or ""
            entry["mode"] = d.get("override_mode") or item.get("proposed_mode") or "append"
            delta = item.get("proposed_frontmatter_delta") or {}
            if delta:
                delta_path = workdir / f"{iid}.fmdelta.yml"
                delta_path.write_text(yaml.safe_dump(delta, sort_keys=False, allow_unicode=True), encoding="utf-8")
                entry["frontmatter_delta_file"] = str(delta_path)

        plan.append(entry)

    plan_path = workdir / "plan.json"
    plan_path.write_text(json.dumps({"plan": plan}, indent=2, ensure_ascii=False))
    return {"plan_path": str(plan_path), "plan": plan}


def _rename_to_path(item: dict, new_name: str | None) -> str | None:
    """If the user supplied a new_name, rebuild the target path in the same folder."""
    if not new_name or not item.get("path"):
        return None
    old = Path(item["path"])
    return str(old.with_name(f"{new_name}.md"))


# ── apply-plan ─────────────────────────────────────────

def apply_plan(plan_json_path: str) -> dict:
    """Execute every entry in plan.json in one call.

    Reads the plan produced by `materialize` and dispatches each
    entry to `write` or `extend` in-process. Returns a per-id
    outcome array so the orchestrator does not have to loop.

    A single failing entry does NOT abort the batch — each result
    is recorded independently so partial progress is visible to
    verify-batch.
    """
    plan_path = Path(plan_json_path)
    data = json.loads(plan_path.read_text())
    entries = data.get("plan", [])

    results = []
    for entry in entries:
        iid = entry.get("id")
        if entry.get("skip"):
            results.append({
                "id": iid,
                "skipped": True,
                "reason": entry.get("reason"),
            })
            continue

        op = entry.get("op")
        try:
            if op == "write":
                r = write(
                    vault_path=entry["target"],
                    body_file=entry["body_file"],
                    frontmatter_file=entry["frontmatter_file"],
                )
            elif op == "extend":
                r = extend(
                    vault_path=entry["target"],
                    section=entry["section"],
                    body_file=entry["body_file"],
                    mode=entry.get("mode", "append"),
                    frontmatter_delta_file=entry.get("frontmatter_delta_file"),
                )
            else:
                results.append({
                    "id": iid,
                    "ok": False,
                    "error": f"unknown op: {op}",
                })
                continue
            results.append({"id": iid, **r})
        except (ValueError, FileNotFoundError, PermissionError) as e:
            results.append({"id": iid, "ok": False, "error": str(e)})

    ok = all(r.get("ok", False) or r.get("skipped") for r in results)
    return {"ok": ok, "results": results}
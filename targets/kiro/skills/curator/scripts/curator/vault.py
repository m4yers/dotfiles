"""Curator vault management — context, git, page CRUD.

Single-file replacement of the former vault/ sub-package.
Sections (in order):
    constants : VAULT_ROOT, READ_ONLY_DIRS, etc.
    config    : tunables
    context   : build_context() for extractors
    git_ops   : commit + recent helpers
    pages     : page CRUD + materialize + apply-plan
    CLI       : typer app exposing context/commit/recent/page subapps

All CLI output is YAML on stdout (the task-runner contract).
"""
from __future__ import annotations


import datetime
import json
import os
import re
import subprocess
import typer
import yaml
from curator.utils import emit, fail
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from typing import Annotated, Optional


# ── vault ─────────────────────────────────────────────



_DEFAULT_VAULT_ROOT = "~/Obsidian/MahVault"
# Resolve at import time so abs_path's startswith check is symlink-
# stable. On hosts where /home is a symlink to /local/home, a lazily-
# computed VAULT_ROOT would stay /home/... while a resolved child
# path would be /local/home/..., breaking the escape check.
VAULT_ROOT = Path(
    os.path.expanduser(os.environ.get("CURATOR_VAULT_ROOT", _DEFAULT_VAULT_ROOT))
).resolve()

# Folder roles. Constants below are the definitive spec for curator
# scope; update them when the vault layout changes.
SOURCES_DIR = "10 SOURCES"
QUOTES_DIR = "11 QUOTES"
KEYWORDS_DIR = "12 KEYWORDS"
PEOPLE_DIR = "13 PEOPLE"
MODELS_DIR = "14 MODELS"
ZETTEL_DIR = "20 ZETTELKASTEN"
SYNTHESIS_DIR = "21 SYNTHESIS"

# Curator write list. Paths under these prefixes are writable.
WRITABLE_PREFIXES = (
    KEYWORDS_DIR,
    PEOPLE_DIR,
    MODELS_DIR,
    SYNTHESIS_DIR,
    f"{SOURCES_DIR}/Papers",
    f"{SOURCES_DIR}/Books",
    f"{SOURCES_DIR}/Articles",
    f"{SOURCES_DIR}/Videos",
)

# Paths under SOURCES that must remain binary / immutable.
BINARY_SUFFIXES = (".pdf", ".epub", ".mp3", ".mp4")

# Folders the curator never writes to, even if the path is under
# a writable prefix as a subtree (belt-and-braces).
READ_ONLY_DIRS = (QUOTES_DIR, ZETTEL_DIR)


@dataclass
class Page:
    path: Path              # absolute
    vault_path: str         # vault-relative
    frontmatter: dict       # parsed yaml, {} if none
    body: str               # text after frontmatter
    raw: str                # full file contents


def abs_path(vault_path: str) -> Path:
    """Resolve a vault-relative path to absolute. Raises on escape."""
    p = (VAULT_ROOT / vault_path).resolve()
    if not str(p).startswith(str(VAULT_ROOT)):
        raise ValueError(f"path escapes vault: {vault_path}")
    return p


def rel_path(abs_p: Path) -> str:
    """Convert absolute path to vault-relative."""
    abs_p = abs_p.resolve()
    return str(abs_p.relative_to(VAULT_ROOT))


def is_writable(vault_path: str) -> bool:
    """True if the curator is allowed to write this path."""
    if any(vault_path.startswith(d + "/") or vault_path == d for d in READ_ONLY_DIRS):
        return False
    # Source binaries are immutable even under writable source folders.
    if any(vault_path.endswith(suf) for suf in BINARY_SUFFIXES):
        return False
    return any(vault_path.startswith(pre + "/") or vault_path == pre for pre in WRITABLE_PREFIXES)


def require_writable(vault_path: str):
    if not is_writable(vault_path):
        raise PermissionError(f"path not writable by curator: {vault_path}")


_FM_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def parse(raw: str) -> tuple[dict, str]:
    """Split yaml frontmatter from body. Returns ({}, raw) if absent.

    Strict: raises ValueError on malformed YAML. Use try_parse() for scans
    that must tolerate vault-wide inconsistencies.
    """
    m = _FM_RE.match(raw)
    if not m:
        return {}, raw
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"invalid frontmatter: {e}")
    if not isinstance(fm, dict):
        raise ValueError("frontmatter must be a mapping")
    return fm, m.group(2)


def try_parse(raw: str) -> tuple[dict, str]:
    """Tolerant variant of parse(). Returns ({}, raw) on any parse error.

    Use in read-only scans (context, stubs, orphans) where one bad
    file must not crash the whole pass.
    """
    try:
        return parse(raw)
    except ValueError:
        return {}, raw


def serialize(frontmatter: dict, body: str) -> str:
    """Produce the on-disk form."""
    if not frontmatter:
        return body
    fm_yaml = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
    return f"---\n{fm_yaml}\n---\n\n{body.lstrip()}"


def load(vault_path: str) -> Page:
    p = abs_path(vault_path)
    if not p.exists():
        raise FileNotFoundError(vault_path)
    raw = p.read_text(encoding="utf-8")
    fm, body = parse(raw)
    return Page(path=p, vault_path=vault_path, frontmatter=fm, body=body, raw=raw)


def save(vault_path: str, frontmatter: dict, body: str):
    require_writable(vault_path)
    p = abs_path(vault_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serialize(frontmatter, body), encoding="utf-8")


def list_md(folder: str) -> list[Path]:
    """List all .md files directly under a vault folder (not recursive)."""
    d = abs_path(folder)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.md"))


def iter_all_md() -> list[Path]:
    """Walk the vault, return all .md files, skipping dotfolders."""
    out = []
    for root, dirs, files in os.walk(VAULT_ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                out.append(Path(root) / f)
    return out


def slugify_basename(name: str) -> str:
    """Vault-safe slug for source filenames. Preserve spaces, hyphens, parens.

    Rule: strip control chars, replace '/' with '—', collapse multiple
    spaces, trim. Preserves readable filenames like
    '1999 Giappaolo - Practical File System Design'.
    """
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = name.replace("/", "—")
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"[:*?\"<>|]", "", name)
    return name

# ── config ────────────────────────────────────────────

# ── Vault scans ───────────────────────────────────────────────────────

# Page staleness threshold for external consumers of vault metadata.
# 90 days ~= one quarter; pages untouched for a full quarter are flagged
# for a refresh pass.
PAGE_STALE_DAYS = 90

# Stub detection: body (after frontmatter) shorter than this is a stub.
# 50 chars ~= a title + one sentence; below this a page carries no
# semantic content beyond the filename.
STUB_BODY_MIN = 50

# Context-build skip: files larger than this skip alias extraction to
# avoid parsing megabyte source notes whose aliases rarely matter for
# dedup. 10 KB is the 99th percentile of existing atomic pages in the
# user's vault.
CONTEXT_FAST_PARSE_LIMIT = 10_000

# ── context ───────────────────────────────────────────



TYPE_TO_FOLDER = {
    "keywords":  KEYWORDS_DIR,
    "people":    PEOPLE_DIR,
    "models":    MODELS_DIR,
    "synthesis": SYNTHESIS_DIR,
}

# Sources are organized in subdirectories by media type. Each
# subdirectory is exposed under a separate context key so extractors
# can match by source kind.
SOURCE_TYPE_TO_FOLDER = {
    "sources_papers":   f"{SOURCES_DIR}/Papers",
    "sources_books":    f"{SOURCES_DIR}/Books",
    "sources_articles": f"{SOURCES_DIR}/Articles",
    "sources_videos":   f"{SOURCES_DIR}/Videos",
}


def build_context(types: list[str] | None = None) -> dict:
    """Return per-folder existing names plus scope rules.

    Default loads every known folder (atomics + sources). Extractors
    use the per-kind list to fill ``match_existing`` fields. Sources
    are split into ``sources_papers``, ``sources_books``,
    ``sources_articles``, ``sources_videos`` so duplicate-ingest
    detection can match by media type.
    """
    all_folders = {**TYPE_TO_FOLDER, **SOURCE_TYPE_TO_FOLDER}
    if types is None:
        types = list(all_folders.keys())

    out: dict = {}
    for t in types:
        folder = all_folders.get(t)
        if not folder:
            raise ValueError(f"unknown type: {t}")
        out[t] = _list_folder(folder)

    out["scope_rules"] = {
        "writable_prefixes": list(WRITABLE_PREFIXES),
        "read_only_dirs":    list(READ_ONLY_DIRS),
        "binary_suffixes":   list(BINARY_SUFFIXES),
    }
    out["vault_root"] = str(VAULT_ROOT)
    return out


def _read_frontmatter(p: Path) -> dict:
    """Read just the YAML frontmatter from a markdown file.

    Frontmatter is at the file head, delimited by ``---`` lines.
    Reading the first 4 KB is enough for any realistic frontmatter
    block; this is much cheaper than reading megabyte source pages.
    """
    try:
        with p.open("rb") as fh:
            head = fh.read(4096).decode("utf-8", errors="replace")
    except OSError:
        return {}
    if not head.startswith("---"):
        return {}
    fm, _ = try_parse(head)
    return fm if isinstance(fm, dict) else {}


def _list_folder(folder: str) -> list[dict]:
    out = []
    for p in list_md(folder):
        size = p.stat().st_size
        fm = _read_frontmatter(p)
        aliases    = fm.get("aliases") or []
        origin_url = fm.get("origin_url")
        published  = fm.get("published_date") or fm.get("date")
        author     = fm.get("author")

        entry = {
            "name":    p.stem,
            "path":    rel_path(p),
            "size":    size,
            "aliases": aliases,
        }
        if origin_url:
            entry["origin_url"] = origin_url
        if published:
            entry["published_date"] = str(published)
        if author:
            entry["author"] = author
        out.append(entry)
    return sorted(out, key=lambda x: x["name"].lower())


# ── CLI ──────────────────────────────────────────────────────────



_CONTEXT_SCHEMA_PATH = (Path(__file__).resolve().parent / "schemas" / "context.schema.json")



def cli_context(
    ctx: typer.Context,
    types: Annotated[Optional[str], typer.Option(
        "--types",
        help="Comma-separated subset: keywords,people,models,synthesis "
             "(default: all)")] = None,
) -> None:
    """Emit vault context (per-folder existing names)."""
    if ctx.invoked_subcommand is not None:
        return
    result = build_context(types=types.split(",") if types else None)
    emit(result)

# ── git_ops ───────────────────────────────────────────



CURATOR_OWNED_GLOBS = (
    "10 SOURCES/Papers",
    "10 SOURCES/Books",
    "10 SOURCES/Articles",
    "10 SOURCES/Videos",
    "12 KEYWORDS",
    "13 PEOPLE",
    "14 MODELS",
    "21 SYNTHESIS",
)


def commit(message: str) -> dict:
    """Stage curator-owned paths, commit with structured message.

    Returns {ok, commit, files} or {ok: false, reason} if nothing to commit.
    """
    _ensure_git_repo()

    # Only stage changes under curator-owned roots.
    subprocess.run(
        ["git", "-C", str(VAULT_ROOT), "add", "--", *CURATOR_OWNED_GLOBS],
        check=True,
    )

    status = subprocess.run(
        ["git", "-C", str(VAULT_ROOT), "diff", "--cached", "--name-status"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    if not status:
        return {"ok": False, "reason": "no changes in curator-owned paths"}

    files = [line.split("\t", 1) for line in status.splitlines()]
    # Build structured message body.
    added = [f for st, f in files if st.startswith("A")]
    modified = [f for st, f in files if st.startswith("M")]
    deleted = [f for st, f in files if st.startswith("D")]

    body_lines = [message, ""]
    if added:
        body_lines.append("added:")
        body_lines.extend(f"  {f}" for f in added)
    if modified:
        body_lines.append("updated:")
        body_lines.extend(f"  {f}" for f in modified)
    if deleted:
        body_lines.append("removed:")
        body_lines.extend(f"  {f}" for f in deleted)
    full_msg = "\n".join(body_lines)

    subprocess.run(
        ["git", "-C", str(VAULT_ROOT), "commit", "-m", full_msg],
        check=True,
    )

    sha = subprocess.run(
        ["git", "-C", str(VAULT_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    return {
        "ok": True,
        "commit": sha,
        "added": added,
        "updated": modified,
        "removed": deleted,
    }


def recent(n: int = 20) -> dict:
    """Recent commits affecting curator-owned paths."""
    _ensure_git_repo()
    fmt = "%h%x09%aI%x09%s"
    r = subprocess.run(
        [
            "git", "-C", str(VAULT_ROOT),
            "log", f"-n{n}", f"--format={fmt}",
            "--", *CURATOR_OWNED_GLOBS,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    entries = []
    for line in r.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            sha, iso, subject = parts
            entries.append({"commit": sha, "date": iso, "subject": subject})
    return {"recent": entries}


def _ensure_git_repo():
    r = subprocess.run(
        ["git", "-C", str(VAULT_ROOT), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise ValueError(
            f"vault is not a git repo. Run `git init` in {VAULT_ROOT} first."
        )


# ── CLI ──────────────────────────────────────────────────────────




# Two top-level commands; each gets its own typer app for mounting
# under the root vault CLI.



def cli_commit(
    ctx: typer.Context,
    message: Annotated[str, typer.Argument(
        help="Commit message subject line.")],
) -> None:
    """Stage curator-owned paths and commit with a structured message."""
    if ctx.invoked_subcommand is not None:
        return
    emit(commit(message))


def cli_recent(
    ctx: typer.Context,
    n: Annotated[int, typer.Option("-n", "--count",
                                      help="Number of commits.")] = 20,
) -> None:
    """Show recent commits affecting curator-owned paths."""
    if ctx.invoked_subcommand is not None:
        return
    emit(recent(n=n))

# ── pages ─────────────────────────────────────────────




# __file__ = <skills>/home/curator/scripts/vault/pages.py
# .parent.parent → <skills>/home/curator/scripts/
_SCRIPTS_ROOT = Path(__file__).resolve().parent


# ── write ──────────────────────────────────────────────

def write(
    vault_path: str,
    body_file: str,
    frontmatter_file: str,
    allow_uncited: bool = False,
) -> dict:
    """Create or overwrite a page. Enforces scope and citation rules."""
    require_writable(vault_path)

    body = Path(body_file).read_text(encoding="utf-8")
    fm_raw = Path(frontmatter_file).read_text(encoding="utf-8")
    fm = yaml.safe_load(fm_raw) or {}
    if not isinstance(fm, dict):
        raise ValueError("frontmatter must be a yaml mapping")

    _ensure_required_frontmatter(fm)
    if not allow_uncited:
        _ensure_cited(fm, body)

    fm.setdefault("last_updated", datetime.date.today().isoformat())

    existed = abs_path(vault_path).exists()
    save(vault_path, fm, body)
    return {
        "ok": True,
        "path": vault_path,
        "action": "overwrote" if existed else "created",
        "bytes": abs_path(vault_path).stat().st_size,
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
    require_writable(vault_path)
    page = load(vault_path)

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

    save(vault_path, new_fm, new_body)
    return {
        "ok": True,
        "path": vault_path,
        "action": f"extended({mode})",
        "section": section,
        "bytes": abs_path(vault_path).stat().st_size,
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
    page = load(vault_path)
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
        paths = list_md(folder)
    else:
        paths = [p for p in iter_all_md()]
    out = []
    for p in paths:
        try:
            raw = p.read_text(encoding="utf-8")
        except Exception:
            continue
        _, body = try_parse(raw)
        if len(body.strip()) < STUB_BODY_MIN:
            out.append({"path": rel_path(p), "size": p.stat().st_size})
    return {"stubs": sorted(out, key=lambda x: x["path"])}


# ── orphans ────────────────────────────────────────────

_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")


def orphans() -> dict:
    """Pages (in writable folders) that no other page links to."""
    all_paths = iter_all_md()
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
        vp = rel_path(p)
        if not _is_writable_folder(vp):
            continue
        if p.stem in link_targets or vp.removesuffix(".md") in link_targets:
            continue
        out.append(vp)
    return {"orphans": sorted(out)}


def _is_writable_folder(vault_path: str) -> bool:
    for d in (KEYWORDS_DIR, PEOPLE_DIR, MODELS_DIR, SYNTHESIS_DIR):
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
        if not abs_path(target).exists():
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
        if t.startswith((SOURCES_DIR, QUOTES_DIR)):
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
    plan_data = {"plan": plan}
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = plan_path.with_suffix(plan_path.suffix + ".tmp")
    tmp.write_text(json.dumps(plan_data, ensure_ascii=False, indent=2))
    os.replace(tmp, plan_path)
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

# ── CLI ──────────────────────────────────────────────────────────





def cli_write(
    vault_path: Annotated[str, typer.Argument()],
    body_file: Annotated[str, typer.Option("--body-file")],
    frontmatter_file: Annotated[str, typer.Option("--frontmatter-file")],
    allow_uncited: Annotated[bool, typer.Option("--allow-uncited")] = False,
) -> None:
    """Create or overwrite a page."""
    try:
        emit(write(vault_path=vault_path,
                    body_file=body_file,
                    frontmatter_file=frontmatter_file,
                    allow_uncited=allow_uncited))
    except (FileNotFoundError, ValueError, PermissionError) as e:
        fail(str(e))


def cli_extend(
    vault_path: Annotated[str, typer.Argument()],
    section: Annotated[str, typer.Option("--section")],
    body_file: Annotated[str, typer.Option("--body-file")],
    mode: Annotated[str, typer.Option("--mode",
        help="append | replace")] = "append",
    frontmatter_delta_file: Annotated[Optional[str], typer.Option(
        "--frontmatter-delta-file")] = None,
) -> None:
    """Extend a page with a section."""
    if mode not in ("append", "replace"):
        fail(f"--mode must be 'append' or 'replace', got {mode!r}")
    try:
        emit(extend(vault_path=vault_path, section=section,
                     body_file=body_file, mode=mode,
                     frontmatter_delta_file=frontmatter_delta_file))
    except (FileNotFoundError, ValueError, PermissionError) as e:
        fail(str(e))


def cli_read(
    vault_path: Annotated[str, typer.Argument()],
    section: Annotated[Optional[str], typer.Option("--section")] = None,
) -> None:
    """Read a page (full or section)."""
    try:
        emit(read(vault_path, section=section))
    except FileNotFoundError as e:
        fail(f"not found: {e}")


def cli_stubs(
    folder: Annotated[Optional[str], typer.Option("--folder")] = None,
) -> None:
    """List 0-byte or minimal pages."""
    emit(stubs(folder=folder))


def cli_orphans() -> None:
    """List pages not linked from anywhere."""
    emit(orphans())


def cli_verify_batch(
    approved_json: Annotated[str, typer.Argument()],
    composed: Annotated[Optional[str], typer.Option("--composed")] = None,
) -> None:
    """Verify all writes in approved.json landed."""
    result = verify_batch(approved_json, composed_json_path=composed)
    emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)


def cli_materialize(
    approved_json: Annotated[str, typer.Argument()],
    composed: Annotated[Optional[str], typer.Option("--composed")] = None,
) -> None:
    """Expand approved proposals into body/frontmatter files + plan."""
    try:
        emit(materialize(approved_json, composed_json_path=composed))
    except (FileNotFoundError, ValueError) as e:
        fail(str(e))


def cli_apply_plan(
    plan_json: Annotated[str, typer.Argument()],
) -> None:
    """Execute every entry in plan.json via write/extend."""
    result = apply_plan(plan_json)
    emit(result)
    if not result.get("ok"):
        raise typer.Exit(code=1)



# ── CLI ──────────────────────────────────────────────────────────

context_app = typer.Typer(
    help="Vault state — what already exists in the vault.",
    invoke_without_command=True,
)
context_app.callback(invoke_without_command=True)(cli_context)


# ── match ────────────────────────────────────────────────────────

# Maps the kind name used in extractor outputs to the vault folder
# the matcher should search.
_KIND_TO_FOLDER = {
    "keywords": KEYWORDS_DIR,
    "people":   PEOPLE_DIR,
    "models":   MODELS_DIR,
}


def _normalize(name: str) -> str:
    """Lowercase + strip + collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", name.lower()).strip()


def find_matches(items: list[dict], folder: str) -> list[dict]:
    """For each item in ``items`` (each must have ``name``), search
    the given vault folder for an existing page whose stem or
    aliases match. Returns a list of {name, match} where ``match``
    is the relative path of the matched page or ``null``.
    """
    candidates = _list_folder(folder)
    by_norm: dict[str, str] = {}
    for c in candidates:
        by_norm[_normalize(c["name"])] = c["path"]
        for alias in c.get("aliases") or []:
            by_norm[_normalize(alias)] = c["path"]

    out: list[dict] = []
    for item in items:
        name = item.get("name", "")
        out.append({
            "name":  name,
            "match": by_norm.get(_normalize(name)),
        })
    return out


def build_match(extractor_outputs: dict[str, str]) -> dict:
    """For each (kind, output_path) pair, load the extractor output
    and find vault matches for its items. Returns a dict keyed by
    kind, each holding a list of {name, match}."""
    out: dict = {}
    for kind, path in extractor_outputs.items():
        folder = _KIND_TO_FOLDER.get(kind)
        if not folder:
            # Topics + summary have no vault folder; emit empty list.
            out[kind] = []
            continue
        if not Path(path).exists():
            out[kind] = []
            continue
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        items = data.get(kind) if isinstance(data, dict) else None
        out[kind] = find_matches(items or [], folder)
    return out


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
    emits a per-kind list of ``{name, match}`` entries where
    ``match`` is the relative vault path of any matching page or
    ``null``."""
    inputs: dict[str, str] = {}
    if keywords: inputs["keywords"] = keywords
    if people:   inputs["people"]   = people
    if models:   inputs["models"]   = models
    if not inputs:
        fail("at least one of --keywords / --people / --models is required")
    emit(build_match(inputs))


commit_app = typer.Typer(
    help="Git commit curator-owned paths.",
    invoke_without_command=True,
)
commit_app.callback(invoke_without_command=True)(cli_commit)

page_app = typer.Typer(
    help="Page operations.",
    no_args_is_help=True,
)
page_app.command("materialize")(cli_materialize)
page_app.command("apply-plan")(cli_apply_plan)
page_app.command("verify-batch")(cli_verify_batch)

app = typer.Typer(
    help="Curator vault management.",
    no_args_is_help=True,
)
app.add_typer(context_app, name="context")
app.command("match")(cli_match)
app.add_typer(commit_app, name="commit")
app.add_typer(page_app, name="page")

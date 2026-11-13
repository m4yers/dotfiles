"""Low-level page primitives — path resolution, frontmatter
parse/serialize, scope checks.

The only functional difference from a plain filesystem write is:

- The zettel-dir exception is NOT gated by this shim; the
  orchestrator MUST verify the user named a zettel before
  calling ``save`` on a zettel path (see SKILL.md Constraints and
  ``references/vault-rules.md``). The scope check here only blocks
  source binaries and ``*.assets/`` subtrees.
- ``list_md`` kept identical.
- New helper ``read`` returns ``{frontmatter, body}`` for
  ``notes.read``.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from vault.config import (
    BINARY_SUFFIXES,
    VAULT_ROOT,
    WRITABLE_PREFIXES,
    ZETTEL_DIR,
)


# ── path resolution ─────────────────────────────────────


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


def _is_writable(vault_path: str) -> bool:
    """True if the agent is allowed to write this path. Private —
    callers go through ``require_writable``.

    The zettel folder is NOT blocked here; the gate is procedural
    (the orchestrator verifies the user named a zettel in
    the request before invoking ``save``). This shim only blocks
    source binaries and ``*.assets/`` subtrees, which are
    immutable regardless of caller.
    """
    # Source binaries are immutable even under writable source folders.
    if any(vault_path.endswith(suf) for suf in BINARY_SUFFIXES):
        return False

    # ``*.assets/`` folders (sibling to a source note) are immutable;
    # the agent never edits them directly. Detect by looking for a
    # ``.assets/`` segment in the path.
    if ".assets/" in vault_path or vault_path.endswith(".assets"):
        return False

    # Zettels are writable via the procedural gate.
    if vault_path.startswith(ZETTEL_DIR + "/") or vault_path == ZETTEL_DIR:
        return True

    return any(vault_path.startswith(pre + "/") or vault_path == pre
                 for pre in WRITABLE_PREFIXES)


def require_writable(vault_path: str):
    """Raise ``PermissionError`` if the agent may not write here."""
    if not _is_writable(vault_path):
        raise PermissionError(
            f"path not writable by vault: {vault_path}")


# ── frontmatter parse / serialize ───────────────────────


_FM_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


def parse(raw: str) -> tuple[dict, str]:
    """Split yaml frontmatter from body. Returns ({}, raw) if absent.

    Strict: raises ValueError on malformed YAML. Use try_parse() for
    scans that must tolerate vault-wide inconsistencies.
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
    """Tolerant variant of parse(). Returns ({}, raw) on any parse
    error.

    Use in read-only scans (matcher folder listing) where one bad
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


# ── page-level CRUD ─────────────────────────────────────


def save(vault_path: str, frontmatter: dict, body: str):
    """Write a page to disk. Enforces write policy."""
    require_writable(vault_path)
    p = abs_path(vault_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(serialize(frontmatter, body), encoding="utf-8")


def read(vault_path: str) -> tuple[dict, str]:
    """Return ``(frontmatter, body)`` for an existing page."""
    p = abs_path(vault_path)
    if not p.exists():
        raise FileNotFoundError(vault_path)
    return parse(p.read_text(encoding="utf-8"))


# ── enumeration ─────────────────────────────────────────


def list_md(folder: str) -> list[Path]:
    """List all .md files directly under a vault folder (not
    recursive)."""
    d = abs_path(folder)
    if not d.is_dir():
        return []
    return sorted(d.glob("*.md"))


# ── slug ────────────────────────────────────────────────


def slugify_basename(name: str) -> str:
    """Vault-safe slug for source filenames. Preserve spaces,
    hyphens, parens.

    Rule: strip control chars, replace '/' with '—', collapse
    multiple spaces, trim. Preserves readable filenames like
    '1999 Giappaolo - Practical File System Design'.
    """
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = name.replace("/", "—")
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"[:*?\"<>|]", "", name)
    return name

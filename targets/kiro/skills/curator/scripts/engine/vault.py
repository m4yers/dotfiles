"""Vault constants, path resolution, frontmatter I/O.

The vault root is ~/Obsidian/MahVault/. All vault-relative
paths in JSON output are relative to this root.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

VAULT_ROOT = Path(os.path.expanduser("~/Obsidian/MahVault"))

# Folder roles. See references/schema.md for the definitive spec.
SOURCES_DIR = "10 SOURCES"
QUOTES_DIR = "11 QUOTES"
KEYWORDS_DIR = "12 KEYWORDS"
PEOPLE_DIR = "13 PEOPLE"
MODELS_DIR = "14 MODELS"
ZETTEL_DIR = "20 ZETTELKASTEN"
SYNTHESIS_DIR = "21 SYNTHESIS"
PROJECTS_DIR = "30 PROJECTS"
MNEMONICS_DIR = "60 MNEMONICS"

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
READ_ONLY_DIRS = (QUOTES_DIR, ZETTEL_DIR, PROJECTS_DIR, MNEMONICS_DIR)


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

    Use in read-only scans (lint, context, stubs, orphans) where one bad
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

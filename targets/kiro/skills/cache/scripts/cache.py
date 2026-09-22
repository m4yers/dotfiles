"""cache.py — content-addressed key/value cache CLI (stdlib only).

Subcommands: key, get, set, del, list, gc, selftest. All storage lives under
_CACHE_ROOT; the cache MUST NOT stat, resolve, open, or otherwise touch any
filesystem path outside that root. `--namespace` is opaque bytes we slugify for
a folder segment; `--part` is opaque bytes we hash for a fragment digest; no
other flag names or reads a filesystem path.

Mode gating (matches project-overview _read_cache/_write_cache verbatim):

    read-write:  reads AND writes allowed
    read-only:   reads allowed, writes and deletes short-circuit to no-op
    write-only:  writes and deletes allowed, reads return empty
    bypass:      all three short-circuit — no I/O at all

Resolution order: `--mode` flag > CACHE_MODE env var > read-write default.
Unknown values exit non-zero rather than silently defaulting.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

# /tmp/kiro-cache — process-scratch root; matches the path referenced from
# SKILL.md's Defaults section. Overridable via KIRO_CACHE_ROOT so the test
# suite can sandbox writes without touching the user's real cache.
_CACHE_ROOT = Path(os.environ.get("KIRO_CACHE_ROOT", "/tmp/kiro-cache"))

# 8 — LRU cap on immediate-child prefixes per namespace. Chosen so
# project-overview's five cached tools fit with headroom (three spare slots
# for stacked working states); raise deliberately when a caller retains more
# generations than that.
_KEEP_KEYS = 8

# 24 — hex chars of sha256 kept for the fragment digest. Enough entropy to
# make collisions astronomically unlikely across a single caller's --part
# tuples while keeping the directory name short enough to type.
_FRAGMENT_HEX_LEN = 24

# 8 — hex chars of sha256 appended to the namespace slug to separate two
# --namespace values that happen to sanitize identically (e.g. "foo/bar" and
# "foo-bar"). Short because slugs are already namespaced by folder position.
_SLUG_HEX_LEN = 8

# 64 — max length of the sanitized portion of a namespace slug before the
# hex suffix. Keeps directory names within POSIX NAME_MAX headroom even after
# appending "-<8hex>" and a trailing separator.
_SLUG_SANITIZED_MAX = 64

# Modes accepted by --mode / CACHE_MODE. Order not significant.
_MODES = ("read-write", "read-only", "write-only", "bypass")

# Chars kept verbatim in a namespace slug — everything else collapses to '-'.
_SLUG_SAFE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


# ------------------------------------------------------------------ helpers


def _die(msg: str, code: int = 2) -> None:
    """Print a diagnostic to stderr and exit."""
    print(f"cache: {msg}", file=sys.stderr)
    sys.exit(code)


def _namespace_slug(namespace: str) -> str:
    """Turn an opaque namespace string into a filesystem-safe folder segment.

    Sanitize [^A-Za-z0-9_.-] → '-', collapse runs, trim leading/trailing '-',
    truncate to _SLUG_SANITIZED_MAX, then append '-<8hex sha256 of the raw
    bytes>' so distinct inputs that sanitize identically still separate.
    Empty result after sanitization is a caller error.
    """
    if not namespace:
        _die("--namespace is required and must be non-empty", code=3)
    raw = namespace.encode("utf-8")
    cleaned = _SLUG_SAFE_RE.sub("-", namespace)
    cleaned = re.sub(r"-+", "-", cleaned).strip("-.")
    cleaned = cleaned[:_SLUG_SANITIZED_MAX].strip("-.")
    if not cleaned:
        # Everything got sanitized away — fall back to a pure hash-prefix slug.
        cleaned = "ns"
    suffix = hashlib.sha256(raw).hexdigest()[:_SLUG_HEX_LEN]
    return f"{cleaned}-{suffix}"


def _fragment_hash(parts: list[str]) -> str:
    """Hash ordered --part fragments into a 24-hex digest.

    Each part is fed as UTF-8 bytes with a single NUL separator so that
    ('ab','c') and ('a','bc') produce distinct digests.
    """
    h = hashlib.sha256()
    for i, p in enumerate(parts):
        if i:
            h.update(b"\0")
        h.update(p.encode("utf-8"))
    return h.hexdigest()[:_FRAGMENT_HEX_LEN]


def _prefix(namespace: str, parts: list[str]) -> str:
    """Compose `<namespace-slug>/<fragment-digest>` for `cache key`."""
    return f"{_namespace_slug(namespace)}/{_fragment_hash(parts)}"


def _validate_key(key: str) -> str:
    """Reject absolute keys and '..' traversal fragments before path join.

    A caller's key is a relative hierarchical path; anything that could climb
    out of _CACHE_ROOT is a bug. We reject at the string layer *before*
    calling pathlib so no clever normalization can smuggle us out.
    """
    if not key:
        _die("<key> is required and must be non-empty", code=3)
    if os.path.isabs(key) or key.startswith("/"):
        _die(f"<key> must be a relative path, got: {key!r}", code=4)
    parts = re.split(r"[/\\]+", key)
    if ".." in parts:
        _die(f"<key> must not contain '..' segments, got: {key!r}", code=4)
    return key


def _resolve_key(key: str, suffix: str = ".yaml") -> Path:
    """Return an absolute path under _CACHE_ROOT for `<key><suffix>`.

    Validates traversal at the string layer, then re-verifies the resolved
    path is a descendant of _CACHE_ROOT to catch anything the string check
    missed (defense in depth). Suffix is *appended* to the key rather than
    substituted, so a key like `foo.bar` maps to `foo.bar.yaml`, not
    `foo.yaml`.
    """
    _validate_key(key)
    base = _CACHE_ROOT.resolve()
    candidate = base / (key + suffix if suffix else key)
    # Path.resolve(strict=False) collapses any residual '..' — if the result
    # is not under base, refuse.
    resolved = candidate.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        _die(f"<key> escapes cache root: {key!r}", code=4)
    return resolved


def _resolve_mode(flag_mode: str | None) -> str:
    """Effective mode: --mode flag > CACHE_MODE env > read-write default."""
    mode = flag_mode or os.environ.get("CACHE_MODE") or "read-write"
    if mode not in _MODES:
        _die(f"unknown --mode/CACHE_MODE value: {mode!r} (want one of "
             f"{', '.join(_MODES)})", code=5)
    return mode


def _read_mode_allows(mode: str) -> bool:
    """Match project-overview _read_cache: read-write and read-only only."""
    return mode in ("read-write", "read-only")


def _write_mode_allows(mode: str) -> bool:
    """Match project-overview _write_cache: read-write and write-only only.

    `cache del` is a write-shaped op and inherits the same gate.
    """
    return mode in ("read-write", "write-only")


def _atomic_write(target: Path, data: bytes) -> None:
    """Write `<target>.tmp` then Path.replace to make the swap atomic.

    Matches project-overview _write_cache: same suffix, same replace call.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)


# ------------------------------------------------------------------ commands


def cmd_key(args: argparse.Namespace) -> int:
    """Emit `<namespace-slug>/<fragment-digest>` on stdout."""
    print(_prefix(args.namespace, args.part or []))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    """Print the stored value on stdout; empty output on miss."""
    mode = _resolve_mode(args.mode)
    if not _read_mode_allows(mode):
        return 0  # bypass / write-only — silent miss
    path = _resolve_key(args.key)
    if not path.is_file():
        return 0
    try:
        sys.stdout.buffer.write(path.read_bytes())
    except OSError as e:
        _die(f"failed to read {args.key}: {e}", code=6)
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    """Read value bytes from stdin and write atomically."""
    mode = _resolve_mode(args.mode)
    if not _write_mode_allows(mode):
        # Drain stdin so the caller's `echo | cache set` doesn't SIGPIPE.
        try:
            sys.stdin.buffer.read()
        except OSError:
            pass
        return 0
    path = _resolve_key(args.key)
    data = sys.stdin.buffer.read()
    _atomic_write(path, data)
    return 0


def cmd_del(args: argparse.Namespace) -> int:
    """Remove the value; exit 0 whether or not it existed."""
    mode = _resolve_mode(args.mode)
    if not _write_mode_allows(mode):
        return 0
    for suffix in (".yaml",):
        path = _resolve_key(args.key, suffix=suffix)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            _die(f"failed to remove {path}: {e}", code=6)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Stream matching keys line-by-line, sorted lexicographically.

    Walks <_CACHE_ROOT>/<prefix>/ and emits every .yaml leaf as its key path
    (relative to _CACHE_ROOT, with the .yaml suffix stripped). Empty output
    when the prefix directory does not exist.
    """
    _validate_key(args.prefix)
    base = _CACHE_ROOT.resolve()
    root = (base / args.prefix).resolve()
    try:
        root.relative_to(base)
    except ValueError:
        _die(f"<prefix> escapes cache root: {args.prefix!r}", code=4)
    if not root.is_dir():
        return 0
    keys: list[str] = []
    for path in root.rglob("*.yaml"):
        rel = path.relative_to(base)
        # Strip .yaml suffix; use posix separators so callers see the same
        # keys they set.
        key = rel.with_suffix("").as_posix()
        keys.append(key)
    for k in sorted(keys):
        print(k)
    return 0


def _iter_namespaces(namespace: str | None) -> list[Path]:
    """Return the list of namespace directories to gc over."""
    if not _CACHE_ROOT.exists():
        return []
    if namespace is not None:
        slug_dir = _CACHE_ROOT / _namespace_slug(namespace)
        return [slug_dir] if slug_dir.is_dir() else []
    return sorted(p for p in _CACHE_ROOT.iterdir() if p.is_dir())


def _recursive_max_mtime(root: Path) -> float:
    """Max mtime seen in any file under `root`; falls back to root's mtime."""
    best = root.stat().st_mtime if root.exists() else 0.0
    for p in root.rglob("*"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if m > best:
            best = m
    return best


def _gc_namespace(ns_dir: Path, keep_keys: int) -> int:
    """Run the LRU sweep on a single namespace directory.

    Returns pruned_prefixes. Uses a non-blocking flock so concurrent runs
    skip rather than contend.
    """
    lock_path = ns_dir / ".gc.lock"
    ns_dir.mkdir(parents=True, exist_ok=True)
    lock_fh = open(lock_path, "a+")
    try:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                return 0
            raise

        return _prune_lru(ns_dir, keep_keys)
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        except OSError:
            pass
        lock_fh.close()


def _prune_lru(ns_dir: Path, keep_keys: int) -> int:
    """Prune immediate-child prefix directories beyond keep_keys, LRU by
    recursive max mtime. Preserves the sentinel `.gc.lock` file.
    """
    children = [p for p in ns_dir.iterdir()
                if p.is_dir() and not p.name.startswith(".")]
    if len(children) <= keep_keys:
        return 0
    ranked = sorted(children, key=_recursive_max_mtime, reverse=True)
    victims = ranked[keep_keys:]
    pruned = 0
    for victim in victims:
        try:
            shutil.rmtree(victim)
            pruned += 1
        except OSError:
            continue
    return pruned


def cmd_gc(args: argparse.Namespace) -> int:
    """Prune one or all namespaces; print the summary count."""
    total_pruned = 0
    for ns_dir in _iter_namespaces(args.namespace):
        total_pruned += _gc_namespace(ns_dir, args.keep_keys)
    print(f"pruned_prefixes={total_pruned}")
    return 0


def cmd_selftest(args: argparse.Namespace) -> int:
    """Exec `python3 -m unittest scripts.test_cache` from the skill root."""
    skill_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "scripts.test_cache"],
        cwd=str(skill_root),
    )
    return proc.returncode


# ------------------------------------------------------------------ parser


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cache",
        description="Content-addressed key/value cache (stdlib only).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    key = sub.add_parser("key", help="derive a <slug>/<fragment> prefix")
    key.add_argument("--namespace", required=True)
    key.add_argument("--part", action="append", default=[])
    key.set_defaults(func=cmd_key)

    get = sub.add_parser("get", help="read a value to stdout (empty on miss)")
    get.add_argument("key")
    get.add_argument("--mode", choices=_MODES)
    get.set_defaults(func=cmd_get)

    st = sub.add_parser("set", help="write value bytes from stdin")
    st.add_argument("key")
    st.add_argument("--mode", choices=_MODES)
    st.set_defaults(func=cmd_set)

    dl = sub.add_parser("del", help="remove a value")
    dl.add_argument("key")
    dl.add_argument("--mode", choices=_MODES)
    dl.set_defaults(func=cmd_del)

    ls = sub.add_parser("list", help="stream matching keys, sorted")
    ls.add_argument("prefix")
    ls.set_defaults(func=cmd_list)

    gc = sub.add_parser("gc", help="prune one or all namespaces")
    gc.add_argument("--namespace", default=None)
    gc.add_argument("--keep-keys", type=int, default=_KEEP_KEYS)
    gc.set_defaults(func=cmd_gc)

    sf = sub.add_parser("selftest", help="run the unittest suite")
    sf.set_defaults(func=cmd_selftest)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except SystemExit:
        raise
    except BrokenPipeError:
        # `cache list | head` closes the pipe; treat as normal completion.
        return 0
    except Exception as e:  # last-resort barrier — surface as exit code
        _die(f"unexpected error: {e}", code=1)
        return 1  # unreachable, satisfies type checkers


if __name__ == "__main__":
    sys.exit(main())

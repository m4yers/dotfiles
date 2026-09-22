---
name: cache
type: interface
description: Content-addressed key/value cache with a script API — get/set/del/list over a single hierarchical S3-style keyspace, atomic writes, cache-mode gating (read-write, read-only, write-only, bypass) via --mode flag or CACHE_MODE env var, `cache key` prefix derivation from a caller-chosen namespace plus opaque --part fragments, and namespace-scoped GC with an LRU cap on immediate child prefixes. Use when any skill or loomv2 tool task needs to cache expensive computed results per caller-defined namespace and identity, or when the user says "cache", "cached results", "cache key", "invalidate cache". Do NOT use for persistent knowledge — use vault instead.
---

# cache

Content-addressed key/value cache. Keys are hierarchical S3-style paths under
a single storage root; values are opaque bytes (typically YAML). Every write
is atomic (`tmp + Path.replace`), reads never take a lock, and only `cache gc`
takes a non-blocking flock. See `references/storage-layout.md` for the on-disk
layout, the slug/fragment derivation formulas, and inspection recipes.

The cache has no git, VCS, workspace, or file-path awareness. `--namespace` is
an opaque string it slugifies into a folder segment; `--part` is opaque bytes it
hashes into a fragment digest; the storage root is the only filesystem location
it ever touches.

## Invocation

```bash
CACHE=~/.kiro/skills/home/cache/scripts/cache.sh
$CACHE <command> [options]
```

The [API](#api) section below is the exhaustive contract — every supported verb
is listed there. Callers do not need to read the script source.

Multi-call scripts SHOULD export `CACHE_MODE` once at the top so every
subsequent `cache get`, `cache set`, and `cache del` inherits it without
threading `--mode` through every invocation:

```bash
export CACHE_MODE=read-only   # or write-only, bypass, read-write
```

An explicit `--mode` flag on a single call overrides the env var for that one
call only.

## API

### key derivation

| Command    | Args                                              | Output                       |
|------------|---------------------------------------------------|------------------------------|
| `key`      | `--namespace <s> [--part <s>]...`                 | `<slug>/<fragment>` on stdout|

### value ops

| Command    | Args                                              | Output                       |
|------------|---------------------------------------------------|------------------------------|
| `get`      | `<key> [--mode M]`                                | value on stdout; empty miss  |
| `set`      | `<key> [--mode M]`                                | — (value from stdin)         |
| `del`      | `<key> [--mode M]`                                | —                            |
| `list`     | `<prefix>`                                        | matching keys, sorted        |

### maintenance

| Command    | Args                                          | Output                             |
|------------|-----------------------------------------------|------------------------------------|
| `gc`       | `[--namespace] [--keep-keys]`                 | `pruned_prefixes=N`          |
| `selftest` | (none)                                        | unittest output                    |

## Commands

### cache key

Derive a `<namespace-slug>/<fragment-digest>` prefix. The caller composes full
keys by appending caller-chosen segments (e.g. `<prefix>/<doc-name>` or a deeper
hierarchy).

```bash
# Code-workspace caller — bump prefix whenever git state changes.
PREFIX=$($CACHE key \
    --namespace project-overview \
    --part "$(git rev-parse HEAD)" \
    --part "$(git diff | sha256sum | cut -d' ' -f1)")

# Non-code caller — date-scoped ticket analysis.
PREFIX=$($CACHE key --namespace ticket-P12345 --part "$(date +%F)")
```

- `--namespace <string>` — opaque namespace label (required). Slugified into
  a folder-safe segment plus an 8-hex sha256 suffix so two labels that
  sanitize identically still separate.
- `--part <string>` — repeatable, ordered. Fed to sha256 with a NUL
  separator; the first 24 hex chars become the fragment digest. Order
  matters — reordering flips the prefix.

Prints exactly one line: the composed prefix. No YAML blob, no cache_dir, no
side effects.

### cache get

Read a value onto stdout. Prints nothing (exit 0) on miss so callers can
distinguish miss from malformed value by output length.

```bash
$CACHE get "$PREFIX/code-inventory"
```

- `<key>` — relative hierarchical path composed from the caller's prefix
  (required). MUST NOT be absolute or contain `..` segments, because a
  key that could climb out of the storage root is a caller bug.
- `--mode M` — one of `read-write`, `read-only`, `write-only`, `bypass`.
  Under `write-only` or `bypass`, `get` short-circuits to empty output.

### cache set

Write value bytes from stdin. Atomic (`<key>.yaml.tmp` then `Path.replace`).

```bash
generate_report | $CACHE set "$PREFIX/report"
```

- `<key>` — same shape rules as `get`.
- `--mode M` — under `read-only` or `bypass`, `set` short-circuits to a
  no-op (stdin is drained to avoid SIGPIPE on the caller).

### cache del

Remove the value file. Exit 0 whether or not the
key existed.

```bash
$CACHE del "$PREFIX/stale-doc"
```

- `<key>` — same shape rules as `get`.
- `--mode M` — under `read-only` or `bypass`, `del` short-circuits to a
  no-op.

### cache list

Stream keys under `<prefix>`, sorted lexicographically, one per line — the S3
SCAN equivalent. Empty output when the prefix has no keys.

```bash
$CACHE list "$PREFIX"
$CACHE list "$(dirname $PREFIX)/files"   # blob side store
```

- `<prefix>` — a hierarchical key prefix; may be the raw namespace slug, a
  full `<slug>/<fragment>` prefix, or a deeper sub-tree.

### cache gc

Prune one or all namespaces. Reports the count of pruned prefixes, uses
non-blocking flock, and returns fast on lock contention.

```bash
$CACHE gc                                    # all namespaces
$CACHE gc --namespace project-overview       # single namespace
$CACHE gc --keep-keys 4                      # tighten the LRU cap
```

- `--namespace <string>` — opaque namespace label; slugified before lookup.
  Omit to gc all namespaces.
- `--keep-keys N` — LRU cap on immediate-child prefix directories per
  namespace (default `8`). Prefixes are ranked by recursive max mtime;
  everything past the cap is removed.

### cache selftest

Exec the unittest suite from the skill root. Exit non-zero if any test fails.

```bash
$CACHE selftest
```

## Defaults

- `--mode` → `read-write` (overridable via `CACHE_MODE`).
- `--keep-keys` → `8` (LRU cap on immediate child prefixes per namespace).
- Cache root → `/tmp/kiro-cache` (override via `KIRO_CACHE_ROOT` for
  tests).

## Rules

- Callers MUST call `cache key` first and compose full keys by appending
  `/<caller-chosen-name>` (or a deeper hierarchy) to the returned prefix,
  because reconstructing the prefix by hand skips fragment hashing and
  drifts across callers.
- `--part` values MUST be passed in a stable order across calls that
  expect to hit the same prefix, because fragments are hashed in the
  order given.
- `cache get`, `cache set`, and `cache del` MUST NOT take locks, because
  content-addressed prefixes make lost-update races write the same bytes
  on both sides and per-key writes are already atomic.
- Only `cache gc` takes a lock, and it MUST use non-blocking flock so
  concurrent runs skip rather than contend.
- The cache MUST NOT stat, resolve, open, or otherwise touch any
  filesystem path outside its storage root, because the isolation
  promise is what lets consumers treat the cache as opaque and lets
  tests sandbox HOME/CWD to prove no side effects escape. `--namespace`
  is opaque bytes it slugifies for a folder name; `--part` is opaque
  bytes it hashes; no other flag names or reads a filesystem path.
- Callers that want to key a value on file contents MUST hash the file
  bytes themselves and pass the digest as a `--part`, because keying on
  mtime or size would silently drop values the caller expected to keep.
- `--mode` on a call overrides `CACHE_MODE`, `CACHE_MODE` overrides the
  `read-write` default. Unrecognized values MUST cause a non-zero exit
  rather than silently defaulting.
- Keys MUST be relative hierarchical paths; absolute keys and `..`
  segments MUST be rejected before path join (traversal defence).

## References

- [`references/storage-layout.md`](references/storage-layout.md) — on-disk
  layout, slug and prefix derivation formulas, and
  inspection recipes with worked migration examples.

## Completion

| Status               | Criteria                                                                  |
|----------------------|---------------------------------------------------------------------------|
| `DONE`               | Value/prefix/list emitted, or `pruned_prefixes=N expired_keys=N` printed. |
| `DONE_WITH_CONCERNS` | `cache gc` skipped due to lock contention.                                |
| `BLOCKED`            | Empty namespace, cache root unwritable, or traversal.                     |
| `NEEDS_CONTEXT`      | Required positional or flag omitted.                                      |

Evidence for `DONE`: value round-tripped, prefix emitted, list produced N lines,
or `pruned_prefixes=N expired_keys=N` summary printed.

Callers MUST stop after 3 consecutive failures of the same operation and report
`BLOCKED` with the last error captured.

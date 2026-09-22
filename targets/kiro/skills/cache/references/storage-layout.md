# Storage Layout

Deep dive on the on-disk shape, derivation formulas, and
inspection recipes. SKILL.md's Rules and Commands sections link here so callers
can stay focused on the API surface.

## Contents

- [1. On-disk layout](#1-on-disk-layout)
- [2. Namespace slug formula](#2-namespace-slug-formula)
- [3. Prefix (fragment) formula](#3-prefix-fragment-formula)
- [4. Worked recipes](#4-worked-recipes)
- [5. Inspection recipes](#5-inspection-recipes)
- [7. Portability](#7-portability)

## 1. On-disk layout

Hierarchical keys map directly to filesystem directories under the cache root;
every value is `<key>.yaml`.

```
/tmp/kiro-cache/
├── project-overview-d5be7a4c/                  ← namespace slug
│   ├── .gc.lock                                ← gc mutex (flock)
│   ├── 585dcf3dfbcf0ccdbce5aead/               ← fragment digest = prefix
│   │   ├── code-inventory.yaml
│   │   ├── build-detect.yaml
│   │   └── deep/
│   │       └── nested/
│   │           └── report.yaml
│   └── files/                                  ← caller-composed sub-tree
│       ├── 3e11c9ab...ff.yaml
│       └── 90ab74cd...12.yaml
└── ticket-P12345-cafeface/
    └── 4a7c9e2b.../
        ├── owls-summary.yaml
        └── root-cause.yaml
```

Notes:

- `.gc.lock` is the only reserved name at the namespace level; the LRU
  pruner ignores it (dot-prefixed).
- The `files/` sub-tree in the diagram is a caller convention, not a
  cache concept — the cache has no "blob store". A caller that wants
  content-addressed storage simply composes keys under a prefix of its
  choice (typically `<slug>/files/<sha>`).

## 2. Namespace slug formula

```
slug = sanitize(namespace) + '-' + first-8-hex(sha256(namespace-utf8))
```

Where `sanitize` replaces every char outside `[A-Za-z0-9_.-]` with `-`,
collapses runs, trims leading/trailing `-`/`.`, and truncates to 64 chars. If
the sanitized portion is empty, the fallback literal `ns` is used before the hex
suffix.

Examples:

| Input                     | Slug                                 |
|---------------------------|--------------------------------------|
| `project-overview`        | `project-overview-d5be7a4c`          |
| `hello world / colon:α`   | `hello-world-colon-<8hex>`           |
| `foo/bar`                 | `foo-bar-<8hex>`                     |
| `foo-bar`                 | `foo-bar-<8hex>` (different sha256)  |
| `///:::`                  | `ns-<8hex>`                          |

The 8-hex suffix keeps `foo/bar` and `foo-bar` apart even though they sanitize
to the same prefix — the raw bytes differ, so the sha256 differs.

## 3. Prefix (fragment) formula

```
fragment = first-24-hex(sha256(part_0 ‖ NUL ‖ part_1 ‖ NUL ‖ ...))
prefix   = slug + '/' + fragment
```

- Each `--part` is fed as UTF-8 bytes, ordered as passed on the CLI.
- Reordering `--part` values flips the fragment; adding a `--part`
  flips it; changing any byte inside a part flips it.
- The NUL separator prevents `("ab", "c")` and `("a", "bc")` from
  colliding.
- 24 hex chars = 96 bits of entropy — collisions across a single
  caller's identity tuples are astronomically unlikely.

## 4. Worked recipes

### Recipe A — project-overview migration

```bash
CACHE=~/.kiro/skills/home/cache/scripts/cache.sh
WS=/path/to/workspace

# Identity: workspace basename + git HEAD + optional dirty-tree hash.
HEAD=$(git -C "$WS" rev-parse HEAD)
DIRTY=$(git -C "$WS" diff | sha256sum | cut -d' ' -f1)

PREFIX=$($CACHE key \
    --namespace project-overview \
    --part "$(basename "$WS")" \
    --part "$HEAD" \
    --part "$DIRTY")

# Store each derived document under the prefix.
generate_inventory | $CACHE set "$PREFIX/code-inventory"
generate_build     | $CACHE set "$PREFIX/build-detect"
generate_tests     | $CACHE set "$PREFIX/test-detect"

# Per-file LLM summaries keyed by git blob sha survive commits — store
# under the SLUG (not under the prefix) so all commits share them:
SLUG=$(echo "$PREFIX" | cut -d/ -f1)
llm_summarize path/to/file.py | $CACHE set "$SLUG/files/$(git ls-files -s path/to/file.py | awk '{print $2}')"
```

### Recipe B — ticket analysis (no filesystem input)

```bash
PREFIX=$($CACHE key --namespace ticket-P12345 --part "$(date +%F)")

fetch_owls    | $CACHE set "$PREFIX/owls-summary"
run_rca       | $CACHE set "$PREFIX/root-cause"
```

The date-scoped `--part` carves generations; gc's LRU cap retires old ones.

## 5. Inspection recipes

```bash
# Everything on disk.
find /tmp/kiro-cache -name '*.yaml' | head

# Recent prefixes in one namespace.
ls -lt /tmp/kiro-cache/project-overview-d5be7a4c/

# Read a value.
cat /tmp/kiro-cache/project-overview-*/*/code-inventory.yaml

# Force a fresh prefix — bump any --part.
$CACHE key --namespace project-overview --part v2   # different fragment

# Purge one namespace by hand (mirrors `cache gc --keep-keys 0`).
rm -rf /tmp/kiro-cache/project-overview-d5be7a4c/
```

## 7. Portability

The redis/S3 vocabulary (GET/SET/DEL/EXPIRE/SCAN, hierarchical keys, per-key
LRU on prefix) survives a swap to sqlite or an actual key-value store with
no CLI changes. Storage stays greppable end-to-end until such a swap is worth
doing: `find … | cat` is the debugger.

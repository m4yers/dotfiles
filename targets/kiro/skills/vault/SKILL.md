---
name: vault
type: workflow
description: Reads, creates, modifies, and deletes notes in the Obsidian vault ~/Obsidian/MahVault from unstructured natural-language requests. Use when the user says "vault", asks to add a quote, source, keyword, person, mental model note, zettel, wiki page, or travel place, or wants to work with the Obsidian vault in any read/modify/write way.
---

# Vault

Meta-level workflow for the Obsidian vault at `~/Obsidian/MahVault`. The
knowledge of **what each folder holds** and **what operations it supports**
lives in the vault itself — one `AGENTS.md` at the vault root, one in every
top-level folder. This skill knows only how to drive those operations:
identify the touched folders, load the right `AGENTS.md`, preview the write,
wait for a directive, and run the write.

## Dependencies

| Name     | Purpose                                      |
|----------|----------------------------------------------|
| `tiling` | activity label and pane layout               |
| `editor` | optional — preview reports to the user       |

## Parameters

- **request** (required): the raw natural-language ask. Captured verbatim
  at Step 1 as `VLT_REQUEST`.

## Constraints

The vault's authoritative rules live in `~/Obsidian/MahVault/AGENTS.md`
and in the `AGENTS.md` of each top-level folder. Format rules, operations
with their Jinja templates, and safety invariants (immutable source
binaries, zettel procedural gate, Obsidian frontmatter rewrites, attachment
layout, no scratch files) live there. The agent MUST read the root
`AGENTS.md` plus the `AGENTS.md` of every touched folder before any
create / modify / delete, because the skill does not duplicate those
rules — Step 2 loads them.

## Workflow

### Step 1: Setup

```bash
VAULT=~/.kiro/skills/home/vault/scripts/vault.sh
VLT_TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh

$VLT_TILING activity set "vault: Setup"
eval "$($VLT_TILING layout build)"
```

Caller state uses the `VLT_` prefix (`VLT_REQUEST`, `VLT_TOUCHED_FOLDERS`)
because bare `VAULT` collides with the shim alias.

1. Capture the user's request verbatim into `VLT_REQUEST`.

Proceed to Step 2.

### Step 2: Scope

```bash
$VLT_TILING activity set "vault: Scope"
```

1. Think hard about which top-level folders the request touches. The
   vault-root `AGENTS.md` lists the folders and what each holds; use its
   `Folders` table as the map. URLs, file paths, and bibliographic cues
   imply `10 SOURCES`; "quote", "passage", "citation" imply `11 QUOTES`;
   "term", "definition", "concept" imply `12 KEYWORDS`; and so on.
2. Load every relevant `AGENTS.md` in one call:
   ```bash
   $VAULT agents <folder-name>... > /tmp/vlt-agents.yaml
   ```
   This returns the root `AGENTS.md` plus one entry per named folder.
3. Locate the matching **Operations** entry in the touched folder's
   `AGENTS.md`. Follow its numbered steps and render its Jinja template
   with concrete values.
4. When the request fits no listed operation, draft an ad-hoc plan from
   the folder's `Structure` and `Maintenance` sections.

Proceed to Step 3.

### Step 3: Plan & confirm

```bash
$VLT_TILING activity set "vault: Plan"
```

1. Follow the Operations entry (or the ad-hoc plan) to produce the
   concrete set of writes. For each note that will be created, modified,
   or deleted, decide the path, frontmatter, and body.
2. Preview as a short bullet list: `created`, `modified`, or `deleted`,
   one per line, with the vault-relative path and a one-line summary
   (new file size, fields changed, reason for delete). Use
   `$VAULT vault write --dry-run` and `$VAULT vault diff-fm` for
   accurate diffs.
3. STOP. Wait for an explicit user directive. Questions without an
   imperative verb MUST NOT trigger writes.

### Step 4: Execute

```bash
$VLT_TILING activity set "vault: Execute"
```

1. On approval, run the writes. Create/modify note bodies via
   `$VAULT vault write`; move/rename/delete via
   `$VAULT vault obsidian move|rename|delete` (the Obsidian app must be
   running). For source ingestion the skill provides
   `$VAULT source fetch` and `$VAULT source convert`; for name matching
   across existing pages, `$VAULT vault match`.
2. After every property edit, run `$VAULT vault diff-fm` to catch
   Obsidian's silent frontmatter rewrites.
3. When the user extends the request mid-run (new quote, another
   keyword, add this too), re-enter Step 3 with the extended preview.

Proceed to Step 5 when all approved writes are complete.

### Step 5: Report

```bash
$VLT_TILING activity set "vault: Done"
```

Print a short bullet list of `created`, `modified`, and `deleted` notes
— vault-relative paths, one per line, no summary paragraph:

```
created  12 KEYWORDS/Flow State.md
modified 10 SOURCES/Articles/Csikszentmihalyi - Flow.md
```

## Rules

1. Questions without an imperative verb MUST be answered without writing
   (no-rush steering); only directives authorize writes.
2. Reports MUST be short bullet lists of created / modified / deleted
   paths (no-yapping steering); no summary paragraphs.
3. Note bodies MUST be written as-is without reflowing lines to a fixed
   width, because Obsidian wraps display lines on its own and hard wraps
   corrupt diffs and make later edits harder.
4. After 3 consecutive shim failures, stop and report BLOCKED with the
   attempted commands.

## Extending the skill

When a request pattern recurs and the agent handles it inconsistently,
the operation belongs in an `AGENTS.md` **Operations** section, not in
the skill. When Obsidian cannot perform a required primitive (fetching a
URL, parsing frontmatter, converting a PDF), the capability belongs in
the skill's `scripts/vault/` package as a generic helper the operations
can invoke.

## Completion

| Status               | Criteria                                                   |
|----------------------|------------------------------------------------------------|
| `DONE`               | All approved writes applied; report printed                |
| `DONE_WITH_CONCERNS` | Some writes applied with user approval, others skipped     |
|                      | (fetch failed, obsidian CLI unavailable)                   |
| `BLOCKED`            | 3 consecutive shim failures, or `vault obsidian` cannot    |
|                      | reach the running Obsidian app                             |
| `NEEDS_CONTEXT`      | Agent could not identify touched folders and user          |
|                      | declined to clarify                                        |

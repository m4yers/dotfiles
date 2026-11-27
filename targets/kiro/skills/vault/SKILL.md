---
name: vault
type: flow
description: Reads, creates, modifies, and deletes notes in the personal Obsidian vault ~/Obsidian/MahVault from unstructured natural-language requests. Use when the user says "Obsidian vault" or "MahVault", asks to add a quote, source, keyword, person, mental model note, zettel, or travel place, or wants to edit a personal wiki note. Routing - personal Obsidian notes come here, Redshift knowledge goes to aws/util/vault, running journals go to live-journal. Do NOT use for the Redshift knowledge base (use aws/util/vault), live journals (use live-journal), or Amazon wiki pages (use wiki-edit).
---

# Vault

Meta-level workflow for the Obsidian vault at `~/Obsidian/MahVault`. The
knowledge of **what each folder holds** and **what operations it supports**
lives in the vault itself — one `AGENTS.md` at the vault root, one in every
top-level folder. This skill knows only how to drive those operations: identify
the touched folders, load the right `AGENTS.md`, preview the write, wait for a
directive, and run the write. All shim commands print YAML on stdout and exit
non-zero on error; `$VAULT --help` and `$VAULT <cmd> --help` carry the CLI
contract.

## Dependencies

- `tiling` — activity tracking.
- `template` — renders the Operations entry's Jinja template with strict
  undefined checks.
- `editor` — optional, preview reports to the user.

## Parameters

- **request** (required): the raw natural-language ask. Captured verbatim at
  Step 1 as `VLT_REQUEST`.

## Aliases

```bash
VLT_TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh
VLT_RENDER=~/.kiro/skills/home/template/scripts/render.sh
VAULT=~/.kiro/skills/home/vault/scripts/vault.sh
```

Caller state uses the `VLT_` prefix (`VLT_REQUEST`, `VLT_TOUCHED_FOLDERS`)
because bare `VAULT` collides with the shim alias.

## Invariants

These hold whatever path the flow takes.

1. The vault's authoritative rules live in `~/Obsidian/MahVault/AGENTS.md` and
   in the `AGENTS.md` of each top-level folder: format rules, operations with
   their Jinja templates, and safety invariants (immutable source binaries,
   zettel procedural gate, Obsidian frontmatter rewrites, attachment layout, no
   scratch files). The agent MUST read the root `AGENTS.md` plus the
   `AGENTS.md` of every touched folder before any create / modify / delete,
   because the skill does not duplicate those rules — Step 2 loads them.
2. Every create, modify, move, rename, or delete MUST be previewed first
   (Step 4) and run only after an explicit user directive, because vault writes
   overwrite notes the user curates by hand. Questions without an imperative
   verb are requests for information, not writes.
3. Note bodies MUST be written as-is without reflowing lines to a fixed width,
   because Obsidian wraps display lines on its own and hard wraps corrupt diffs
   and make later edits harder.
4. After every property edit, the agent MUST check the frontmatter with
   `$VAULT vault diff-fm` (or the `fm_diff` block `vault write` returns)
   against a baseline, because Obsidian silently rewrites frontmatter on save.
5. Adaptations MUST stay inside invariants 1–4. A request that would break one
   ("just write it, skip the preview") MUST be confirmed with the operator
   first, in one line naming the invariant.
6. Announce each adaptation in one line before acting, e.g. "No Operations
   entry fits; drafting an ad-hoc plan from Structure" or "Re-entering Step 4,
   the request grew".
7. After 3 failed attempts at one check (frontmatter restore in Step 5,
   wikilink verification in Step 6) or 3 consecutive shim failures, stop and
   report `BLOCKED` with the attempted commands.

## Workflow

The steps below are the default path. The operator MAY redirect at any point:
skip, repeat, reorder, or add a step. Announce each change in one line before
acting, and confirm first when it would break an invariant.

### Step 1: Setup

Goal: capture the request and open the pane layout.

```bash
$VLT_TILING activity set "vault(<request-summary>): Setup"
eval "$($VLT_TILING layout build)"
```

1. Capture the user's request verbatim into `VLT_REQUEST`.

Proceed to Step 2.

### Step 2: Scope

Goal: know which folders the request touches and load their rules.

```bash
$VLT_TILING activity set "vault(<request-summary>): Scope"
```

1. Think hard about which top-level folders the request touches. Use the
   `Folders` table in the vault-root `AGENTS.md` as the map. Record them in
   `VLT_TOUCHED_FOLDERS`.
2. If no folder matches, STOP and wait for the user to name the folder. If the
   user declines, end with `NEEDS_CONTEXT`.
3. Load every relevant `AGENTS.md` in one call and read the YAML from stdout:
   ```bash
   $VAULT agents <folder-name>...
   ```
   The command exits non-zero and names the folder when any `AGENTS.md` is
   missing or unreadable; on non-zero exit, stop and report the error.

Proceed to Step 3.

### Step 3: Plan

Goal: turn the request into a concrete set of writes.

```bash
$VLT_TILING activity set "vault(<request-summary>): Plan"
```

1. Find the matching **Operations** entry in the touched folder's `AGENTS.md`
   and follow its numbered steps.
2. When the request fits no listed operation, announce it (invariant 6) and
   draft an ad-hoc plan from the folder's `Structure` and `Maintenance`
   sections.
3. Save the entry's Jinja template to a file and render it with the concrete
   values into the body file `vault write` will take:
   ```bash
   $VLT_RENDER --template <template-file> --json-vars <vars.json> > <body-file>
   ```
   A non-zero exit means a missing or unused variable; fix the vars, do not
   hand-edit the output.
4. For each note that will be created, modified, moved, renamed, or deleted,
   decide the path, frontmatter, and body (or source and destination).

Proceed to Step 4.

### Step 4: Preview and confirm

Goal: show the exact writes and get an explicit directive.

```bash
$VLT_TILING activity set "vault(<request-summary>): Preview and confirm"
```

1. For every create or modify, save the dry-run output to a per-note preview
   file; it is the reference Step 5 checks the real write against:
   ```bash
   $VAULT vault write --dry-run <vault-path> --frontmatter <json> \
       --body-file <body-file> > <preview-file>
   ```
   The per-note calls have no dependencies; make them in parallel.
2. For every create or modify, validate the proposed frontmatter against the
   folder's rules; add `--require <key>` for each extra field the Operations
   entry demands:
   ```bash
   $VAULT vault validate <vault-path> --frontmatter <json> [--require <key>]...
   ```
   Pass is exit 0. On exit 1, fix the frontmatter from `missing` and `errors`
   and re-run 4.1 for that note.
3. Preview as a short bullet list: `created`, `modified`, `moved`, `renamed`, or
   `deleted`, one per line, with the vault-relative path and a one-line summary
   (new file size, fields changed, reason for delete) taken from the preview
   files.
4. STOP and wait for the user's explicit directive before any write; end the
   turn after the preview (invariant 2).

On approval, proceed to Steps 5–7 as the plan needs. On requested changes,
re-run Step 3. On rejection, go to Step 8 with no writes.

### Step 5: Write notes

Goal: apply approved creates and modifies, exactly as previewed.

```bash
$VLT_TILING activity set "vault(<request-summary>): Write notes"
```

1. Re-run the dry-run of 4.1 into a second file and compare it with the saved
   preview:
   ```bash
   $VAULT vault write --dry-run <vault-path> --frontmatter <json> \
       --body-file <body-file> > <recheck-file>
   cmp -s <preview-file> <recheck-file>
   ```
   Pass is `cmp` exit 0. On mismatch the note changed since the preview:
   announce it and re-enter Step 4 for that note.
2. Write the note. Pass `--zettel` only when the user named a zettel in the
   request; without it, writes under `20 ZETTELKASTEN/` are refused:
   ```bash
   $VAULT vault write <vault-path> --frontmatter <json> --body-file <body-file>
   ```
3. Read `fm_diff.changed` from the write envelope. Pass is `false`.
4. On `true`, warn the user with the `modified` entries, then restore the
   rewritten fields with another `vault write` carrying the intended
   frontmatter.
5. Re-check `fm_diff.changed` on the restore; after 3 failed attempts, end with
   `BLOCKED` (invariant 7).

### Step 6: Move, rename, delete

Goal: run Obsidian-side operations so wikilinks are rewritten, and verify it.

```bash
$VLT_TILING activity set "vault(<request-summary>): Move, rename, delete"
```

1. Confirm the source still exists and capture its frontmatter:
   ```bash
   $VAULT vault read <src> > <baseline-file>
   ```
   Pass is exit 0. On `not found`, stop and report the missing note.
2. Run the operation (the Obsidian app must be running):
   ```bash
   $VAULT vault obsidian move <src> <dst>
   $VAULT vault obsidian rename <src> <new-name>
   $VAULT vault obsidian delete <path>
   ```
3. For move and rename, read `fm_diff.changed` from the envelope. Pass is
   `false`; on `true`, warn and restore the fields as in Step 5.4.
4. Verify the wikilink rewrite: search for links to the old name and expect no
   hits:
   ```bash
   $VAULT vault search "[[<old-stem>"
   ```
   Pass is an empty list. On hits, warn the user and retry the operation;
   after 3 failed attempts, end with `BLOCKED` (invariant 7).

### Step 7: Ingest sources

Goal: bring an external source into the vault and extract its text.

```bash
$VLT_TILING activity set "vault(<request-summary>): Ingest sources"
```

1. Fetch the source; the shim saves the artifact in the vault and persists the
   fetch envelope in its cache:
   ```bash
   $VAULT source fetch <url-or-path>
   ```
2. Convert it; `http_headers` from the fetch envelope reach `metadata` without
   any file passing:
   ```bash
   $VAULT source convert <path>
   ```
   Read `converted_path` for the extracted text.
3. Match extracted names against existing pages before planning new ones
   (`$VAULT vault match --help` gives the input shape):
   ```bash
   $VAULT vault match --keywords <file> --people <file> --models <file>
   ```
   A non-empty `skipped` list means some pages' aliases were unreadable; tell
   the user before creating a page whose `match` is null.

When the user extends the request mid-run (new quote, another keyword, add this
too), announce it and re-enter Step 4 with the extended preview. Proceed to
Step 8 when all approved writes are complete.

### Step 8: Report

Goal: list what changed.

```bash
$VLT_TILING activity set "vault(<request-summary>): Report"
```

1. Print a short bullet list of `created`, `modified`, `moved`, `renamed`, and
   `deleted` notes — vault-relative paths, one per line, no summary paragraph:
   ```
   created  12 KEYWORDS/Flow State.md
   modified 10 SOURCES/Articles/Csikszentmihalyi - Flow.md
   ```

## Completion

| Status               | Criteria                                                   |
|----------------------|------------------------------------------------------------|
| `DONE`               | All approved writes applied; report printed                |
| `DONE_WITH_CONCERNS` | Some writes applied with user approval, others skipped     |
|                      | because a source fetch or convert failed                   |
| `BLOCKED`            | 3 failed attempts at one check, 3 consecutive shim         |
|                      | failures, or `vault obsidian` cannot reach the running     |
|                      | Obsidian app                                               |
| `NEEDS_CONTEXT`      | Agent could not identify touched folders and user          |
|                      | declined to clarify                                        |

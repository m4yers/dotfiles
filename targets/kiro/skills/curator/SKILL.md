---
name: curator
type: workflow
description: Curates an Obsidian vault as an LLM wiki on top of Zettelkasten. Use when the user says "ingest", "curate", "lint vault", or provides a URL or source path to add to ~/Obsidian/MahVault. Fetches a source (PDF, YouTube, HTML, local file), extracts atomic pages (keywords, people, models) and synthesis overviews via parallel sub-agents, then gates all writes on user approval. Do NOT use for writing personal zettels — those live in 20 ZETTELKASTEN/ and are human-only.
---

# Curator — LLM Wiki for MahVault

Maintains the LLM-writable layers of `~/Obsidian/MahVault/`: atomic
entity pages (`12 KEYWORDS`, `13 PEOPLE`, `14 MODELS`) and synthesis
overviews (`21 SYNTHESIS`). Never writes to the Zettelkasten, quotes,
or personal layers.

## Dependencies

- `home/tiling` — pane layout and activity tracking
- `home/skill-analytics` — invocation logging
- `home/template` — render jinja2 templates via `render.sh`

## Parameters

- **operation** (required): `ingest` or `lint`
- **url-or-path** (required for `ingest`): http(s) URL or a local
  file path inside `~/Obsidian/MahVault/10 SOURCES/`
- **--topic** (optional for `ingest`): topic hint steering the
  extractors (e.g. `--topic "LoRA optimization"` narrows which
  aspects of a multi-topic source to extract)
- **--media** (optional for `ingest`): content-type override; valid
  values are listed by `source.sh fetch --help` (and enumerated in
  `source/content_types.py`)
- **--scope** (optional for `lint`): `KEYWORDS` | `PEOPLE` |
  `MODELS` | `SYNTHESIS` | `all` (default: `all`)

## Workflow

### Step 1: Initialize & Route

1. Derive the provisional target, set tiling activity, log activation.
   `$TARGET` is re-assigned from `fetched.basename` in Step 2.3 and
   used unchanged by every later step:
   ```bash
   SKILLS=~/.kiro/skills
   case "<operation>" in
       ingest) TARGET=$(basename "<url-or-path>") ;;
       lint)   TARGET=lint ;;
   esac
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Initialize & Route"
   $SKILLS/home/skill-analytics/scripts/add-invocation.sh \
       curator user:$(whoami)
   ```
2. Parse the user's input. Two operations exist:
   - `ingest <url-or-path> [--topic X]` — full pipeline
   - `lint [--scope KEYWORDS|PEOPLE|MODELS|SYNTHESIS|all]` — health
     check only, no ingest

On `ingest`: proceed to Step 2.
On `lint`: jump to Step 8.

### Step 2: Acquire & Convert Source

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Acquire & Convert Source"
   ```
2. Create the workdir (disk tool owns the lifecycle); capture the
   printed path into `$WD` for downstream calls:
   ```bash
   WD=$($SKILLS/home/curator/scripts/disk.sh workdir create "$TARGET")
   ```
3. Fetch the source and re-assign `$TARGET` from the returned
   JSON. See `scripts/disk/schemas/fetch-envelope.schema.json`
   for the envelope shape; run `source.sh fetch --help` for `--media`
   values:
   ```bash
   $SKILLS/home/curator/scripts/source.sh \
       fetch "<url-or-path>" --workdir "$WD" \
       [--media <type>] [--topic "<topic>"]
   TARGET="<fetched.basename>"
   ```
4. Convert the fetched source to `<wd>/source.md` and load vault
   context (independent calls — can run in parallel):
   ```bash
   $SKILLS/home/curator/scripts/source.sh \
       convert "<fetched.path>" --workdir "$WD"
   ```
   ```bash
   $SKILLS/home/curator/scripts/vault.sh context
   ```

On completion: proceed to Step 3.

### Step 3: Extract + Judge (shared retry budget ≤ 3)

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Extract + Judge"
   ```

2. Render extractor prompts, then dispatch one `curator-extractor`
   sub-agent per entry in the returned `.prompts` map
   (`subagent` blocking mode, in parallel). Each sub-agent
   receives the contents of the file at the emitted path as its
   prompt. A builder schema failure counts against the failing
   kind's budget:
   ```bash
   render_out=$($SKILLS/home/curator/scripts/disk.sh render-extractor-prompts \
       "<workdir>" \
       --source-vault-path "<fetched.path>" \
       --content-type "<fetched.content_type>" \
       [--topic "<topic>"])
   # for each (kind, path) in "$render_out" | jq '.prompts':
   #   dispatch curator-extractor with prompt = $(cat "$path")
   ```

3. Render judge prompts, then dispatch one `curator-judge`
   sub-agent per entry in the returned `.prompts` map, in
   parallel. Each sub-agent receives the contents of the file at
   the emitted path as its prompt. For each kind whose verdict is
   REJECT when `attempts < 3`, re-render its extractor prompt (the
   retry command returns a single `.prompt` path that overwrites
   the kind's slot) and return to sub-step 2 for that kind. At
   attempts = 3 stop retrying:
   ```bash
   judge_out=$($SKILLS/home/curator/scripts/disk.sh render-judge-prompts \
       "<workdir>" \
       --source-vault-path "<fetched.path>" \
       --content-type "<fetched.content_type>" --attempt <N> \
       [--topic "<topic>"])
   # for each (kind, path) in "$judge_out" | jq '.prompts':
   #   dispatch curator-judge with prompt = $(cat "$path")
   #
   # per failing kind, before returning to sub-step 2:
   retry_out=$($SKILLS/home/curator/scripts/disk.sh render-retry-extractor-prompt \
       "<workdir>" --kind <kind> \
       --source-vault-path "<fetched.path>" --prior-attempt <N> \
       --content-type "<fetched.content_type>" [--topic "<topic>"])
   # re-dispatch curator-extractor for <kind> with prompt =
   # $(cat "$(jq -r .prompt <<<"$retry_out")")
   ```

4. Aggregate per-attempt verdicts into `<workdir>/verdicts/<kind>.json`.
   Non-zero exit: treat as an extractor failure and re-dispatch:
   ```bash
   for kind in summary sources keywords people models; do
       $SKILLS/home/curator/scripts/disk.sh aggregate-verdicts \
           "<workdir>" --kind "$kind" --attempts "<attempts_made>" \
           [--schema-failure N|"<message>"]
   done
   ```

On completion: proceed to Step 4.

### Step 4: Compose Report

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Compose Report"
   ```

2. Render the composer prompt (composer receives extractor outputs
   and verdict files as separate inputs — no pre-merging):
   ```bash
   $SKILLS/home/curator/scripts/disk.sh render-composer-prompt \
       "<workdir>" \
       --schema-path "<scripts/disk/schemas/composed.schema.json>" \
       --context-json "<context-json>"
   ```

3. Dispatch `curator-composer` via `subagent`. On schema failure
   from any builder call, re-dispatch with the error attached to
   the prompt. The composer prompt at
   `templates/composer-prompt.j2` is the builder contract;
   `compose-merge-issues` in `builders.py` documents the post-run
   id-pairing rules.

4. Merge judge issues onto composed items. Non-zero exit means an
   id mismatch (composer bug); re-dispatch the composer:
   ```bash
   $SKILLS/home/curator/scripts/disk.sh \
       compose-merge-issues "<workdir>"
   ```

On completion: proceed to Step 5.

### Step 5: Gate on User Approval

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Gate on User Approval"
   ```

2. Build report-vars.json and render the report:
   ```bash
   $SKILLS/home/curator/scripts/disk.sh \
       report-vars "<workdir>/composed.json" \
       -o "<workdir>/report-vars.json"
   $SKILLS/home/template/scripts/render.sh \
       --template $SKILLS/home/curator/scripts/disk/templates/report.md.j2 \
       --json-vars "<workdir>/report-vars.json"
   ```
   Show the rendered output to the user. STOP and wait for the user
   to review.

3. Ask the user for a decision per item: approve / edit / deny /
   rename / redirect. For each user answer, call the approved
   builder — first `approved-init` once, then
   `approved-add-decision` per item:
   ```bash
   $SKILLS/home/curator/scripts/disk.sh \
       approved-init --workdir "<workdir>"
   # for each decision:
   $SKILLS/home/curator/scripts/disk.sh \
       approved-add-decision --workdir "<workdir>" \
       --id <id> --action approve|edit|deny|rename|redirect \
       [--override-body-file ...] [--override-path ...] ...
   ```

On approval: proceed to Step 6.

### Step 6: Apply Approved Plan

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Apply Approved Plan"
   ```

2. Materialize approved proposals into body + frontmatter files:
   ```bash
   $SKILLS/home/curator/scripts/vault.sh \
       page materialize "<workdir>/approved.json"
   ```

3. Execute every plan entry in one call. Non-zero exit: report
   BLOCKED before committing:
   ```bash
   $SKILLS/home/curator/scripts/vault.sh \
       page apply-plan "<workdir>/plan.json"
   ```

4. Verify every file landed. Non-zero: report BLOCKED before
   commit:
   ```bash
   $SKILLS/home/curator/scripts/vault.sh \
       page verify-batch "<workdir>/approved.json"
   ```

On completion: proceed to Step 7.

### Step 7: Commit & Sweep

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Commit & Sweep"
   ```

2. Commit the vault:
   ```bash
   $SKILLS/home/curator/scripts/vault.sh \
       commit "ingest: <source-basename>"
   ```

3. Print the follow-up source list from `composed.related_sources`:
   ```bash
   jq -r '.related_sources[] | "- \(.type): \(.title)"' \
       "<workdir>/composed.json"
   ```

4. Sweep the workdir:
   ```bash
   $SKILLS/home/curator/scripts/disk.sh \
       workdir sweep "<workdir>"
   ```

5. Set tiling activity to Done:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Done"
   ```

On completion: report status from the Completion table.

### Step 8: Lint Vault Health

Runs standalone (no ingest). Reports health issues as proposals the
user applies manually.

1. Set tiling activity:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Lint Vault Health"
   ```

2. Run the linter:
   ```bash
   $SKILLS/home/curator/scripts/vault.sh \
       lint [--scope <scope>]
   ```
   Output categories: see `vault.sh lint --help`.

3. Present the report to the user. STOP and wait for user input.
   Ask the user per category whether to act. Misfiled migrations
   require explicit per-item approval because they move files
   between folders.

4. Set tiling activity to Done:
   ```bash
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator($TARGET): Done"
   ```

On completion: report status.

## Rules

1. Every page written to `12/13/14/21` MUST include a `sources:`
   frontmatter field listing at least one vault-relative path under
   `10 SOURCES/` or `11 QUOTES/`. Uncited pages are rejected by
   `page write`.

2. Links flow one direction: `21 → {10, 11, 12, 13, 14, 20}` and
   `20 → {10, 11, 12}`. Keep source notes clean of back-references.

3. Source binary files (`.pdf`, `.epub`) and asset folders
   (`*.assets/`) are immutable to the curator.

4. The transient markdown at `/tmp/curator/<date>/<slug>/source.md`
   is for extractor input only and MUST be deleted at the end of
   each ingest (Step 7.4) because keeping it around makes
   `.md` references ambiguous between source-of-truth and scratch.

5. Retry up to 3 consecutive extractor failures before reporting
   BLOCKED. Sub-agent output that fails JSON or schema validation
   counts as a failure.

6. User approval is required for every vault write. The curator
   MUST NOT auto-apply any proposal without an entry in
   `approved.json` because silent writes remove the user's veto
   over vault content.

## Completion

| Status               | Criteria                                  |
|----------------------|-------------------------------------------|
| `DONE`                 | Source ingested, approved pages written,  |
|                      | commit made, workdir swept, follow-up     |
|                      | list printed                              |
| `DONE_WITH_CONCERNS`   | Ingest complete but some extractors       |
|                      | returned partial data or user denied all  |
|                      | proposals                                 |
| `BLOCKED`              | Fetch, convert, or extractor failed 3     |
|                      | times, or user declined to approve any    |
|                      | changes and asked to abort                |
| `NEEDS_CONTEXT`        | URL/path missing, or vault path not set   |

- The curator MUST stop after 3 consecutive failures and report
  BLOCKED with what was tried.

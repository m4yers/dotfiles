---
name: curator
type: workflow
description: Curate an Obsidian vault as an LLM wiki on top of Zettelkasten. Use when the user says "ingest", "curate", "lint vault", or provides a URL or source path to add to ~/Obsidian/MahVault. Fetches a source (PDF, YouTube, HTML, local file), extracts atomic pages (keywords, people, models) and synthesis overviews via parallel sub-agents, then gates all writes on user approval. Do NOT use for writing personal zettels — those live in 20 ZETTELKASTEN/ and are human-only.
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

- **url-or-path** (required for `ingest`): http(s) URL or a local
  file path inside `~/Obsidian/MahVault/10 SOURCES/`
- **--topic** (optional): topic hint steering the extractors

## Workflow

### Step 1: Initialize & Route

1. Set tiling activity and log activation. `<target>` is the source
   basename once known, or `init` before parsing:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(init): Initialize & Route"
   $SKILLS/home/skill-analytics/scripts/add-invocation.sh \
       curator user:$(whoami)
   ```
2. Parse the user's input. Two operations exist:
   - `ingest <url-or-path> [--topic X]` — full pipeline
   - `lint [--scope KEYWORDS|PEOPLE|MODELS|SYNTHESIS|all]` — health
     check only, no ingest

On `ingest`: proceed to Step 2.
On `lint`: jump to Step 7.

### Step 2: Acquire & Convert Source

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(<basename>): Acquire & Convert Source"
   ```
2. Fetch the source:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       fetch "<url-or-path>"
   ```

3. Convert and load context in parallel (independent calls):
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       convert "<path>"
   ```
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh context
   ```

On completion: proceed to Step 3.

### Step 3: Extract Proposals (parallel sub-agents)

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(<basename>): Extract Proposals"
   ```

2. Render each extractor prompt via the template skill, then dispatch
   all five extractors in parallel through the `subagent` tool
   (blocking mode, no `depends_on`). One render + one dispatch per
   extractor.

   Extractor roster — agent names match the JSON files in
   `~/.kiro/agents/`:

   ```
   curator-summary   → writes summary.json
   curator-sources   → writes sources.json
   curator-keywords  → writes keywords.json
   curator-people    → writes people.json
   curator-models    → writes models.json
   ```

   Render the prompt for each extractor:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/template/scripts/render.sh \
       --template $SKILLS/home/curator/templates/extractor-prompt.j2 \
       --var agent_role=<role> \
       --var source_md_path=<workdir>/source.md \
       --var source_vault_path=<fetched.path> \
       --var output_path=<workdir>/<type>.json \
       --var schema_path=<schemas-path> \
       --var existing_names=<context-slice-json> \
       --var page_anatomy=<anatomy-from-page-types>
   ```
   Then invoke `subagent` with each rendered prompt.

3. Validate the five JSON outputs:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       validate "<workdir>"
   ```
   Non-zero exit: report BLOCKED.

On completion: proceed to Step 4.

### Step 4: Compose Report

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(<basename>): Compose Report"
   ```

2. Render the composer prompt. Composer is the only reasoning-heavy
   step — the ultrathink cue in the template forces edge-case dedup
   across extractors.
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/template/scripts/render.sh \
       --template $SKILLS/home/curator/templates/composer-prompt.j2 \
       --var workdir=<workdir> \
       --var context_json=<context-json> \
       --var schema_path=<schemas/composed.schema.json>
   ```

3. Dispatch `curator-composer` via `subagent`. Output lands at
   `<workdir>/composed.json`.

4. Validate composed.json:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       validate-schema composed "<workdir>/composed.json"
   ```

On completion: proceed to Step 5.

### Step 5: Gate on User Approval

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(<basename>): Gate on User Approval"
   ```

2. Render the report via the template skill:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/template/scripts/render.sh \
       --template $SKILLS/home/curator/templates/report.md.j2 \
       --var summary=<composed.summary> \
       --var keywords=<composed.proposals.keywords> \
       --var people=<composed.proposals.people> \
       --var models=<composed.proposals.models> \
       --var synthesis=<composed.proposals.synthesis> \
       --var related_sources=<composed.related_sources>
   ```
   Show the rendered output to the user. STOP and wait for the
   user to review.

3. Ask the user for a decision per item: approve / edit / deny /
   rename / redirect. Write to `<workdir>/approved.json`.

4. Validate approved.json:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       validate-schema approved "<workdir>/approved.json"
   ```

On approval: proceed to Step 6.

### Step 6: Apply & Commit

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(<basename>): Apply & Commit"
   ```

2. Materialize approved proposals into body + frontmatter files,
   then execute every plan entry in one call:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       page materialize "<workdir>/approved.json"
   $SKILLS/home/curator/scripts/engine.sh \
       page apply-plan "<workdir>/plan.json"
   ```
   `apply-plan` dispatches each entry to `page write` or
   `page extend` and returns a per-id outcome array. Non-zero
   exit: report BLOCKED before committing.

3. Verify every file landed, then commit:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       page verify-batch "<workdir>/approved.json"
   $SKILLS/home/curator/scripts/engine.sh \
       commit "ingest: <source-basename>"
   ```
   Non-zero verify: report BLOCKED before commit.

4. Print `composed.related_sources` as the follow-up list, then
   sweep the workdir:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       sweep "<workdir>"
   ```

5. Set tiling activity to Done:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(<basename>): Done"
   ```

On completion: report status from the Completion table.

### Step 7: Lint Vault Health

Runs standalone (no ingest). Reports health issues as proposals the
user applies manually.

1. Set tiling activity:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(lint): Lint Vault Health"
   ```

2. Run the linter:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/curator/scripts/engine.sh \
       lint [--scope <scope>]
   ```
   Output categories: see `references/schema.md`.

3. Present the report to the user. For each category, ask whether
   to act. Misfiled migrations require explicit per-item approval
   because they move files between folders.

4. Set tiling activity to Done:
   ```bash
   SKILLS=~/.kiro/skills
   $SKILLS/home/tiling/scripts/run-ttm.sh \
       activity set "curator(lint): Done"
   ```

On completion: report status.

## References

- `references/schema.md` — folder roles, scope, citation rules,
  frontmatter spec
- `references/page-types.md` — anatomy of keyword/person/model/
  synthesis pages
- `references/handlers.md` — per-URL-type ingestion recipes
- `references/agents.md` — sub-agent roster, prompts, JSON output
  schemas

## Rules

1. The curator MUST NOT write to `11 QUOTES/`, `20 ZETTELKASTEN/`,
   `30 PROJECTS/`, `60 MNEMONICS/`, or root-level notes, because
   those layers carry your voice and the LLM rewriting them erases
   nuance that cannot be recovered.

2. Every page written to `12/13/14/21` MUST include a `sources:`
   frontmatter field listing at least one vault-relative path under
   `10 SOURCES/` or `11 QUOTES/`. Uncited pages are rejected by
   `page write`.

3. Links flow one direction: `21 → {10, 11, 12, 13, 14, 20}` and
   `20 → {10, 11, 12}`. Keep source notes clean of back-references.

4. Source binary files (`.pdf`, `.epub`) and asset folders
   (`*.assets/`) are immutable to the curator.

5. The transient markdown at `/tmp/curator/<date>/<slug>/source.md`
   is for extractor input only and MUST be deleted at the end of
   each ingest (Step 6.4) because keeping it around makes
   `.md` references ambiguous between source-of-truth and scratch.

6. Retry up to 3 consecutive extractor failures before reporting
   BLOCKED. Sub-agent output that fails JSON or schema validation
   counts as a failure.

7. User approval is required for every vault write. The curator
   MUST NOT auto-apply any proposal without an entry in
   `approved.json` because silent writes remove the user's veto
   over vault content.

8. Use `subagent` only for the named extractors and the composer.
   All other steps (script calls, file reads, parsing user
   decisions, JSON validation) run directly in the orchestrator,
   because delegating mechanical ops to sub-agents costs tokens
   without adding reasoning.

## Completion

| Status               | Criteria                                  |
|----------------------|-------------------------------------------|
| `DONE`               | Source ingested, approved pages written,  |
|                      | commit made, workdir swept, follow-up     |
|                      | list printed                              |
| `DONE_WITH_CONCERNS` | Ingest complete but some extractors       |
|                      | returned partial data or user denied all  |
|                      | proposals                                 |
| `BLOCKED`            | Fetch, convert, or extractor failed 3     |
|                      | times, or user declined to approve any    |
|                      | changes and asked to abort                |
| `NEEDS_CONTEXT`      | URL/path missing, or vault path not set   |

- The curator MUST stop after 3 consecutive failures and report
  BLOCKED with what was tried.

---
name: skill-reviewer
type: workflow
description: Audits a Kiro skill for convention, model-aware, and pattern issues, then drives a human gate to accept or decline findings. Use when the user says "review skill", "audit skill", "check skill quality", or wants to verify a skill meets conventions. Do NOT use for creating skills — use skill-builder instead.
---

# Skill-Reviewer

Drives loom to audit a skill. The orchestrator's job: drive
`$REVIEWER next/complete`, dispatch each yielded agent task, and run the human
gate. Loom handles plan, rendering, validation, and skip logic.

## Parameters

- **name** (required): kebab-case skill name to review.
- **category** (optional): `home`, `aws`, `dev`, `diagnostics`, or `util` —
  searches all if not given.

## Workflow

### Step 1: Ingest

1. Set up tooling aliases:
   ```bash
   SKILLS=~/.kiro/skills
   REVIEWER=$SKILLS/home/skill-reviewer/scripts/skill-reviewer.sh
   TILING=$SKILLS/home/tiling/scripts/run-ttm.sh
   EDITOR=$SKILLS/home/editor/scripts/run-editor.sh
   ANALYTICS=$SKILLS/home/skill-analytics/scripts/add-invocation.sh
   ```
2. Set tiling activity, record invocation, build layout:
   ```bash
   $TILING activity set "skill-reviewer(<name>): Ingest"
   $ANALYTICS skill-reviewer user:$(whoami)
   eval "$($TILING layout build)"
   ```
3. Ingest:
   ```bash
   WD=$($REVIEWER ingest <name> [--category <category>])
   ```
4. If `ingest` fails: NEEDS_CONTEXT.

### Step 2: Drive the loop

```bash
$TILING activity set "skill-reviewer(<name>): Drive the loop"
```

Loop until done:

1. Run `$REVIEWER next "$WD"`. Parse the YAML response.
2. If `done: true` → break.
3. If `stuck: true` → BLOCKED.
4. Otherwise, for each `ready[].id`:
   - If `id == gate` → drive the human gate (see helper).
   - Else → dispatch the agent (see helper).
   - Then `$REVIEWER complete "$WD" <id>`.

Independent ids in one batch can be dispatched in parallel.

```bash
$TILING activity set "skill-reviewer(<name>): Done"
```

## Helper: Dispatch agent task

`$REVIEWER next` yields ready agent tasks with their `prompt_path` already
rendered. For each id, dispatch via the `subagent` MCP tool with `role: trusted`
(grants file-read access to skill directories).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its own output via
`loom output add` (the prompt instructs how). After dispatch returns, call
`$REVIEWER complete "$WD" "<id>"`.

Dispatch independent ids in parallel via the `subagent` `stages` array with no
`depends_on`.

## Helper: Drive human gate

`gate` is a human-kind task. Drive it conversationally: show the report, take
fix instructions from the user, apply them, and record decisions via tooling.
The report file is the canonical accept/decline record;
`pipeline gate-decisions` later parses it back into the gate output.

1. Set tiling activity and ensure layout:
   ```bash
   $TILING activity set "skill-reviewer(<name>): Human gate"
   eval "$($TILING layout build)"
   ```
2. Open the report file in the editor (not the gate prompt — the report is where
   findings live):
   ```bash
   REPORT=$($REVIEWER status "$WD" \
       | python3 -c 'import sys,yaml; print(yaml.safe_load(sys.stdin)["report_path"])')
   $EDITOR show file "$REPORT"
   ```
3. STOP and wait for the user. The user names findings (by id or short title)
   and tells the orchestrator either to fix (with guidance if needed) or to
   decline (with reason).
4. For each finding the user names:
   - **Accept**: apply the fix to the skill (edit files directly, keep the
     change minimal — only what the finding describes), then mark accepted
     because the report is the canonical decision record:
     ```bash
     $REVIEWER report accept "$WD" <finding-id>
     ```
   - **Decline**: record the decline with the user's reason:
     ```bash
     $REVIEWER report decline "$WD" <finding-id> \
         --reason "<text>"
     ```
   Re-show the report after each batch so the user sees the current state:
   ```bash
   $EDITOR show file "$REPORT"
   ```
5. When the user signals proceed, parse the report markers into the gate output
   and complete the gate:
   ```bash
   $REVIEWER pipeline gate-decisions "$WD" \
       > "$WD/tasks/*-gate/output.yaml"
   $REVIEWER complete "$WD" gate
   ```

## Rules

1. Dispatch kind=agent tasks via `subagent`. Tool/human tasks the orchestrator
   never sees in `ready`; loom runs tools inline and yields humans for the gate
   driver.
2. The gate MUST be human-driven. Auto-approving removes the user's veto.
3. Findings the user did not mark remain open — never mark them declined.
   Silence is not rejection.

## Completion

| Status          | Criteria                                                |
| --------------- | ------------------------------------------------------- |
| `DONE`          | Gate completed; user-named findings applied or declined |
| `BLOCKED`       | `next` / `complete` errored, or stuck plan reported     |
| `NEEDS_CONTEXT` | Skill name not provided or ingest rejected input        |

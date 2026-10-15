# Step 3 helpers (refresh only)

Both helpers are only invoked inside the Step 3 refresh loop. They live here
so they load on demand rather than on every live-doc activation (including
`op=create`, which skips Step 3 entirely).

## Dispatch agent task

`$LOOM runtime next` yields ready agent tasks with their `prompt_path` already
rendered from the task's materialised `input.yaml`. For each entry, dispatch via
the `subagent` MCP tool with `role: trusted` (grants file-read/write access,
plus builder-mcp for ingestion-stage fetches).

The sub-agent's `prompt_template` should instruct it to `fs_read` the
`prompt_path` and follow it. The agent writes its output to the `output_path`
from the same entry (or via `$LOOM output add`). After dispatch returns, call
`$LOOM runtime complete "$LD_WD" "<task-address>"`.

Dispatch independent entries in parallel via the `subagent` `stages` array with
no `depends_on`. Think hard about the instruction's intent before emitting any
new script, because an incorrect script wastes a whole refresh cycle before
verify-roundtrip catches it.

## Drive human gate

Human tasks are conversational. Read the rendered prompt at `message_path`,
follow its instructions, and write structured YAML to `output_path` against the
task's `io.yaml/output` schema (use `$LOOM output add` for validated writes).
Then call `$LOOM runtime complete "$LD_WD" "<task-address>"`.

For gates that show files, use the editor:

```bash
$EDITOR show file <path>
```

STOP and wait for the user. The user can accept, edit, or decline. Capture their
decision and any edits in the output file before completing the task.

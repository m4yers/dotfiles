# Subagent Completion

When operating as a sub-agent (spawned via `use_subagent`),
always call the summary tool to report findings back to the
main agent before ending the task. Do not end without
summarizing results — the main agent cannot see your work
otherwise.

# Model-Aware Authoring

Claude 4.6 is significantly more proactive than earlier models.
Skills should account for these tendencies:

**Constraint tone.** Write constraints in normal, direct language.
"Use this tool when investigating cluster issues" is better than
"CRITICAL: You MUST use this tool whenever investigating cluster
issues!" The model follows plain instructions reliably — heavy
emphasis causes overtriggering.

**Overthinking.** Investigative workflows (rca, cr-review) may
benefit from a constraint like: "Choose an approach and commit to
it. Do not revisit the decision unless new evidence directly
contradicts it." This prevents the model from over-exploring when
a single path would suffice.

**Subagent overuse.** Skills that delegate to subagents should
specify when direct action is preferred. The model has a strong
tendency to spawn subagents even for simple tasks like reading a
file or running grep. Add guidance like: "Use subagents only for
parallel independent workstreams. For sequential single-file
operations, work directly."

**Overengineering.** Code-generating skills should include a
minimality constraint: "Only make changes that are directly
requested or clearly necessary. Do not add abstractions, helpers,
or defensive code for hypothetical scenarios." Without this, the
model tends to create extra files and unnecessary layers.

**Thinking cues.** Trigger words nudge the model toward deeper
reasoning. Use them in skill constraints where the quality of
reasoning matters:

| Cue            | Depth                  |
|----------------|------------------------|
| think          | Small reasoning boost  |
| think hard     | Medium reasoning       |
| think harder   | Extended reasoning     |
| ultrathink     | Maximum depth          |

Drop them naturally into constraints: "Ultrathink about the root
cause before proposing a fix." All research and investigation
tasks should use "ultrathink" to ensure thorough exploration.

**Parallel tool hints.** Skills that invoke multiple independent
tools (reading several files, running queries) should note when
calls can be parallelized: "These reads have no dependencies —
make all calls in parallel." This boosts throughput without
requiring the model to infer independence.

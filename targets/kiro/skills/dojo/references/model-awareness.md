# Model Awareness

Rules that account for Claude 4.6 behaviour and context cost.

## Contents

- [1. Behaviour Tendencies](#1-behaviour-tendencies)
- [2. Token Budget](#2-token-budget)

## 1. Behaviour Tendencies

1. Constraints MUST be written in plain, direct language, because heavy emphasis
   (uppercase warnings, exclamation marks) causes overtriggering.
2. Investigative skills (RCA, CR review) SHOULD include a commit-and-move
   constraint — e.g., "Choose an approach and commit to it; do not revisit
   unless new evidence directly contradicts it" — to prevent over-exploration.
3. Skills that delegate to sub-agents MUST specify when direct action is
   preferred, because without guidance the model spawns sub-agents even for
   simple tasks like reading a file or running grep.
4. Sub-agents SHOULD be used only for parallel independent workstreams;
   sequential single-file operations MUST be done directly.
5. Code-generating skills MUST include a minimality constraint — e.g., "Only
   make changes that are directly requested or clearly necessary; do not add
   abstractions, helpers, or defensive code for hypothetical scenarios" —
   because without it the model creates extra files and unnecessary layers.
6. Skills SHOULD use thinking-cue trigger words to nudge reasoning depth per the
   table below, dropping them naturally into constraints (e.g., "Ultrathink
   about the root cause before proposing a fix").
7. Research and investigation skills SHOULD use "ultrathink" to ensure thorough
   exploration.
8. Skills that invoke multiple independent tools (file reads, queries) MUST note
   when calls can be parallelized — e.g., "These reads have no dependencies;
   make all calls in parallel" — because otherwise the model serializes
   independent calls.

| Cue          | Depth                 |
| ------------ | --------------------- |
| think        | Small reasoning boost |
| think hard   | Medium reasoning      |
| think harder | Extended reasoning    |
| ultrathink   | Maximum depth         |

## 2. Token Budget

1. Authors MUST account for context cost when placing rules: steering rules cost
   tokens in every conversation; SKILL.md body only when the skill activates;
   reference files only when explicitly read.
2. A new steering rule MUST be useful in the majority of conversations,
   otherwise the rule MUST live in a skill, because steering pays the cost on
   every turn.
3. Before creating a new skill, authors MUST ask whether an existing skill can
   be broadened instead, because every new skill adds routing cost.
4. Content needed only in specific workflow steps MUST be moved to `references/`
   and loaded on demand, because SKILL.md body is paid whenever the skill
   activates.

| Artifact        | When loaded          | Cost   |
| --------------- | -------------------- | ------ |
| Steering file   | Every conversation   | High   |
| Skill name+desc | Every conversation   | Low    |
| SKILL.md body   | When skill activated | Medium |
| Reference file  | When explicitly read | Low    |

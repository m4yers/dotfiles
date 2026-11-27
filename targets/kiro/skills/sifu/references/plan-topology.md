# Plan Topology

Task DAGs for the three sifu op graphs, rendered by `$LOOM visualise`. The
`audit` entry is the `loom-audit/` subgraph; its child tasks appear under
it. Legend: ○ tool · ◆ agent · ▣ human · ↻ loop.

## Contents

- [1. Create](#1-create)
- [2. Update](#2-update)
- [3. Review](#3-review)
## 1. Create

```text
○          29 publish-output
├─┬─┬─┬─╮
│ │ │ │ ▣  28 final-review
│ ╭───┬─╯
│ │ │ ◆  27 skill-modify
│ ├───╯
│ ○ │                          26 audit-core/publish-output
│ ├───┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │  15 audit-core/audit-check-authoring
│ ╭───┬─╯ │ │ │ │ │ │ │ │ │ │
│ │ │ │   ◆ │ │ │ │ │ │ │ │ │  16 audit-core/audit-check-model-awareness
│ ╭───┬───╯ │ │ │ │ │ │ │ │ │
│ │ │ │     ◆ │ │ │ │ │ │ │ │  17 audit-core/audit-check-scripts
│ ╭───┬─────╯ │ │ │ │ │ │ │ │
│ │ │ │       ◆ │ │ │ │ │ │ │  18 audit-core/audit-check-secure-llm
│ ╭───┬───────╯ │ │ │ │ │ │ │
│ │ │ │         ◆ │ │ │ │ │ │  19 audit-core/audit-check-interface
│ ╭───┬─────────╯ │ │ │ │ │ │
│ │ │ │           ◆ │ │ │ │ │  20 audit-core/audit-check-tool
│ ╭───┬───────────╯ │ │ │ │ │
│ │ │ │             ◆ │ │ │ │  21 audit-core/audit-check-workflow
│ ╭───┬─────────────╯ │ │ │ │
│ │ │ │               ◆ │ │ │  22 audit-core/audit-check-reference
│ ╭───┬───────────────╯ │ │ │
│ │ │ │                 ◆ │ │  23 audit-core/audit-check-flow
│ ╭───┬─────────────────╯ │ │
│ │ │ │                   ◆ │  24 audit-core/audit-design
│ ╭───┬───────────────────╯ │
│ │ │ │                     ◆  25 audit-core/audit-design-update
│ ╭───┬─────────────────────╯
│ │ │ ○  14 audit-core/audit-autochecks
│ ├───╯
│ ○ │    13 audit-core/ingest-input
│ ├───╮
│ ○ │ │  12 find-skill
╭─┴─╮ │
│   ◆ │  11 skill-materialize
│   ├─╮
│   │ ↻  10 design-accept   ↻ loop → design-author · fuel 5 · while …
│ ╭───┤
│ ▣ │ │    09 design-review
│ ├─────╮
│ ○ │ │ │  07 design-render
│ ├───╯ │
│ │ │   ○  08 design-checks
│ ├─────╯
│ ◆ │      06 design-author
╭─┼─┬─┬─╮
│ │ │ ○ │  03 check-name
╭─┬───╯ │
│ │ ○   │  04 check-location
╭─┬─╯   │
│ │     ○  05 check-overlaps
╭─┬─────╯
│ ▣  02 gather-create
├─╯
○  01 ingest-input
```

## 2. Update

```text
○          25 publish-output
├─┬─┬─┬─╮
│ │ │ │ ▣  24 final-review
│ ╭───┬─╯
│ │ │ ◆  23 skill-modify
│ ├───╯
│ ○ │                          22 audit-core/publish-output
│ ├───┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │  11 audit-core/audit-check-authoring
│ ╭───┬─╯ │ │ │ │ │ │ │ │ │ │
│ │ │ │   ◆ │ │ │ │ │ │ │ │ │  12 audit-core/audit-check-model-awareness
│ ╭───┬───╯ │ │ │ │ │ │ │ │ │
│ │ │ │     ◆ │ │ │ │ │ │ │ │  13 audit-core/audit-check-scripts
│ ╭───┬─────╯ │ │ │ │ │ │ │ │
│ │ │ │       ◆ │ │ │ │ │ │ │  14 audit-core/audit-check-secure-llm
│ ╭───┬───────╯ │ │ │ │ │ │ │
│ │ │ │         ◆ │ │ │ │ │ │  15 audit-core/audit-check-interface
│ ╭───┬─────────╯ │ │ │ │ │ │
│ │ │ │           ◆ │ │ │ │ │  16 audit-core/audit-check-tool
│ ╭───┬───────────╯ │ │ │ │ │
│ │ │ │             ◆ │ │ │ │  17 audit-core/audit-check-workflow
│ ╭───┬─────────────╯ │ │ │ │
│ │ │ │               ◆ │ │ │  18 audit-core/audit-check-reference
│ ╭───┬───────────────╯ │ │ │
│ │ │ │                 ◆ │ │  19 audit-core/audit-check-flow
│ ╭───┬─────────────────╯ │ │
│ │ │ │                   ◆ │  20 audit-core/audit-design
│ ╭───┬───────────────────╯ │
│ │ │ │                     ◆  21 audit-core/audit-design-update
│ ╭───┬─────────────────────╯
│ │ │ ○  10 audit-core/audit-autochecks
│ ├───╯
│ ○ │    09 audit-core/ingest-input
│ ├─┬─╮
│ │ ◆ │  08 modify-changes
│ ╭─┴─╮
│ │   ↻  07 design-accept-update   ↻ loop → design-author-update · fuel 5 · while …
│ │ ╭─┤
│ │ ▣ │  06 design-review-update
│ │ ○ │  05 design-render-update
│ │ ├─╯
│ │ ◆  04 design-author-update
│ ╭─┤
│ │ ▣  03 gather-update
│ ├─╯
│ ○  02 find-skill
├─╯
○  01 ingest-input
```

## 3. Review

```text
○      20 publish-output
├─┬─╮
│ │ ↻    19 skill-fix-apply   ↻ loop → show-report · fuel 10 · while …
│ │ ├─╮
│ │ │ ▣  18 skill-fix-review
│ │ ├─╯
│ │ ○  17 show-report
│ ├─╯
│ ○                          16 audit-core/publish-output
│ ├─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ │ │ ◆ │ │ │ │ │ │ │ │ │ │  05 audit-core/audit-check-authoring
│ ╭─┬─╯ │ │ │ │ │ │ │ │ │ │
│ │ │   ◆ │ │ │ │ │ │ │ │ │  06 audit-core/audit-check-model-awareness
│ ╭─┬───╯ │ │ │ │ │ │ │ │ │
│ │ │     ◆ │ │ │ │ │ │ │ │  07 audit-core/audit-check-scripts
│ ╭─┬─────╯ │ │ │ │ │ │ │ │
│ │ │       ◆ │ │ │ │ │ │ │  08 audit-core/audit-check-secure-llm
│ ╭─┬───────╯ │ │ │ │ │ │ │
│ │ │         ◆ │ │ │ │ │ │  09 audit-core/audit-check-interface
│ ╭─┬─────────╯ │ │ │ │ │ │
│ │ │           ◆ │ │ │ │ │  10 audit-core/audit-check-tool
│ ╭─┬───────────╯ │ │ │ │ │
│ │ │             ◆ │ │ │ │  11 audit-core/audit-check-workflow
│ ╭─┬─────────────╯ │ │ │ │
│ │ │               ◆ │ │ │  12 audit-core/audit-check-reference
│ ╭─┬───────────────╯ │ │ │
│ │ │                 ◆ │ │  13 audit-core/audit-check-flow
│ ╭─┬─────────────────╯ │ │
│ │ │                   ◆ │  14 audit-core/audit-design
│ ╭─┬───────────────────╯ │
│ │ │                     ◆  15 audit-core/audit-design-update
│ ╭─┬─────────────────────╯
│ │ ○  04 audit-core/audit-autochecks
│ ├─╯
│ ○  03 audit-core/ingest-input
│ ○  02 find-skill
├─╯
○  01 ingest-input
```

# Plan Topology

Task DAGs for the three sifu op graphs, rendered by `$LOOM visualise`. The
`audit-core` entry is the `loom-audit/` subgraph; its child tasks appear under
it: `audit-topics` → `audit-checks` pick the rules, `audit-shard-plan` (loop
header) fills 16 slots, `audit-shard-01..16` judge them, `audit-aggregate`
(latch) loops while checks remain. Legend: ○ tool · ◆ agent · ▣ human · ↻ loop.

## Contents

- [1. Create](#1-create)
- [2. Update](#2-update)
- [3. Review](#3-review)

## 1. Create

```text
○          40 publish-output
├─┬─┬─┬─╮
│ │ │ │ ▣  39 final-review
│ ╭───┬─╯
│ │ │ ◆  38 skill-modify
│ ├───╯
│ ○ │          37 audit-core/publish-output
│ ├───┬─┬─┬─╮
│ │ │ │ ↻ │ │                                34 audit-core/audit-aggregate   ↻ loop → audit-core/audit-shard-plan · fuel 8 · while …
│ │ │ │ ├─────┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │  18 audit-core/audit-shard-01
│ │ │ │ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │ │ │ │ │  19 audit-core/audit-shard-02
│ │ │ │ ├─────╯ │ │ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │   ◆ │ │ │ │ │ │ │ │ │ │ │ │ │  20 audit-core/audit-shard-03
│ │ │ │ ├───────╯ │ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │     ◆ │ │ │ │ │ │ │ │ │ │ │ │  21 audit-core/audit-shard-04
│ │ │ │ ├─────────╯ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │       ◆ │ │ │ │ │ │ │ │ │ │ │  22 audit-core/audit-shard-05
│ │ │ │ ├───────────╯ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │         ◆ │ │ │ │ │ │ │ │ │ │  23 audit-core/audit-shard-06
│ │ │ │ ├─────────────╯ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │           ◆ │ │ │ │ │ │ │ │ │  24 audit-core/audit-shard-07
│ │ │ │ ├───────────────╯ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │             ◆ │ │ │ │ │ │ │ │  25 audit-core/audit-shard-08
│ │ │ │ ├─────────────────╯ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │               ◆ │ │ │ │ │ │ │  26 audit-core/audit-shard-09
│ │ │ │ ├───────────────────╯ │ │ │ │ │ │ │
│ │ │ │ │ │ │                 ◆ │ │ │ │ │ │  27 audit-core/audit-shard-10
│ │ │ │ ├─────────────────────╯ │ │ │ │ │ │
│ │ │ │ │ │ │                   ◆ │ │ │ │ │  28 audit-core/audit-shard-11
│ │ │ │ ├───────────────────────╯ │ │ │ │ │
│ │ │ │ │ │ │                     ◆ │ │ │ │  29 audit-core/audit-shard-12
│ │ │ │ ├─────────────────────────╯ │ │ │ │
│ │ │ │ │ │ │                       ◆ │ │ │  30 audit-core/audit-shard-13
│ │ │ │ ├───────────────────────────╯ │ │ │
│ │ │ │ │ │ │                         ◆ │ │  31 audit-core/audit-shard-14
│ │ │ │ ├─────────────────────────────╯ │ │
│ │ │ │ │ │ │                           ◆ │  32 audit-core/audit-shard-15
│ │ │ │ ├───────────────────────────────╯ │
│ │ │ │ │ │ │                             ◆  33 audit-core/audit-shard-16
│ │ │ │ ├─────────────────────────────────╯
│ │ │ │ ○ │ │  17 audit-core/audit-shard-plan
│ │ │ ╭─┤ │ │
│ │ │ │ │ ◆ │  35 audit-core/audit-design
│ ╭───┬───╯ │
│ │ │ │ │   ◆  36 audit-core/audit-design-update
│ ╭───┬─────╯
│ │ │ ○ │  14 audit-core/audit-autochecks
│ ├───╯ │
│ │ │   ○  16 audit-core/audit-checks
│ │ │   ○  15 audit-core/audit-topics
│ ├─────╯
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

legend: ○ tool · ◆ agent · ▣ human · ↻ loop   │ all-dep · ╷ any-dep   when:/↻ inline
```

## 2. Update

```text
○          38 publish-output
├─┬─┬─┬─╮
│ │ │ │ ▣  37 final-review
│ ╭───┬─┤
│ │ │ │ ○  10 check-overlaps
│ │ │ │ ○  09 find-skill-updated → find-skill
╭───┬───╯
│ │ │ ◆  36 skill-modify
│ ├───╯
│ ○ │          35 audit-core/publish-output
│ ├───┬─┬─┬─╮
│ │ │ │ ↻ │ │                                32 audit-core/audit-aggregate   ↻ loop → audit-core/audit-shard-plan · fuel 8 · while …
│ │ │ │ ├─────┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │  16 audit-core/audit-shard-01
│ │ │ │ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │ │ │ │ │  17 audit-core/audit-shard-02
│ │ │ │ ├─────╯ │ │ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │   ◆ │ │ │ │ │ │ │ │ │ │ │ │ │  18 audit-core/audit-shard-03
│ │ │ │ ├───────╯ │ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │     ◆ │ │ │ │ │ │ │ │ │ │ │ │  19 audit-core/audit-shard-04
│ │ │ │ ├─────────╯ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │       ◆ │ │ │ │ │ │ │ │ │ │ │  20 audit-core/audit-shard-05
│ │ │ │ ├───────────╯ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │         ◆ │ │ │ │ │ │ │ │ │ │  21 audit-core/audit-shard-06
│ │ │ │ ├─────────────╯ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │           ◆ │ │ │ │ │ │ │ │ │  22 audit-core/audit-shard-07
│ │ │ │ ├───────────────╯ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │             ◆ │ │ │ │ │ │ │ │  23 audit-core/audit-shard-08
│ │ │ │ ├─────────────────╯ │ │ │ │ │ │ │ │
│ │ │ │ │ │ │               ◆ │ │ │ │ │ │ │  24 audit-core/audit-shard-09
│ │ │ │ ├───────────────────╯ │ │ │ │ │ │ │
│ │ │ │ │ │ │                 ◆ │ │ │ │ │ │  25 audit-core/audit-shard-10
│ │ │ │ ├─────────────────────╯ │ │ │ │ │ │
│ │ │ │ │ │ │                   ◆ │ │ │ │ │  26 audit-core/audit-shard-11
│ │ │ │ ├───────────────────────╯ │ │ │ │ │
│ │ │ │ │ │ │                     ◆ │ │ │ │  27 audit-core/audit-shard-12
│ │ │ │ ├─────────────────────────╯ │ │ │ │
│ │ │ │ │ │ │                       ◆ │ │ │  28 audit-core/audit-shard-13
│ │ │ │ ├───────────────────────────╯ │ │ │
│ │ │ │ │ │ │                         ◆ │ │  29 audit-core/audit-shard-14
│ │ │ │ ├─────────────────────────────╯ │ │
│ │ │ │ │ │ │                           ◆ │  30 audit-core/audit-shard-15
│ │ │ │ ├───────────────────────────────╯ │
│ │ │ │ │ │ │                             ◆  31 audit-core/audit-shard-16
│ │ │ │ ├─────────────────────────────────╯
│ │ │ │ ○ │ │  15 audit-core/audit-shard-plan
│ │ │ ╭─┤ │ │
│ │ │ │ │ ◆ │  33 audit-core/audit-design
│ ╭───┬───╯ │
│ │ │ │ │   ◆  34 audit-core/audit-design-update
│ ╭───┬─────╯
│ │ │ ○ │  12 audit-core/audit-autochecks
│ ├───╯ │
│ │ │   ○  14 audit-core/audit-checks
│ │ │   ○  13 audit-core/audit-topics
│ ├─────╯
│ ○ │    11 audit-core/ingest-input
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

legend: ○ tool · ◆ agent · ▣ human · ↻ loop   │ all-dep · ╷ any-dep   when:/↻ inline
```

## 3. Review

```text
○      32 publish-output
├─┬─╮
│ │ ↻  31 skill-fix-count   ↻ loop → show-report · fuel 10 · while …
│ │ ◆    30 skill-fix-apply
│ │ ├─╮
│ │ │ ▣  29 skill-fix-review
│ │ ├─╯
│ │ ○  28 show-report
│ ├─╯
│ ○          27 audit-core/publish-output
│ ├─┬─┬─┬─╮
│ │ │ ↻ │ │                                24 audit-core/audit-aggregate   ↻ loop → audit-core/audit-shard-plan · fuel 8 · while …
│ │ │ ├─────┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ │ │ ◆ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │  08 audit-core/audit-shard-01
│ │ │ │ │ │ ◆ │ │ │ │ │ │ │ │ │ │ │ │ │ │  09 audit-core/audit-shard-02
│ │ │ ├─────╯ │ │ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │   ◆ │ │ │ │ │ │ │ │ │ │ │ │ │  10 audit-core/audit-shard-03
│ │ │ ├───────╯ │ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │     ◆ │ │ │ │ │ │ │ │ │ │ │ │  11 audit-core/audit-shard-04
│ │ │ ├─────────╯ │ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │       ◆ │ │ │ │ │ │ │ │ │ │ │  12 audit-core/audit-shard-05
│ │ │ ├───────────╯ │ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │         ◆ │ │ │ │ │ │ │ │ │ │  13 audit-core/audit-shard-06
│ │ │ ├─────────────╯ │ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │           ◆ │ │ │ │ │ │ │ │ │  14 audit-core/audit-shard-07
│ │ │ ├───────────────╯ │ │ │ │ │ │ │ │ │
│ │ │ │ │ │             ◆ │ │ │ │ │ │ │ │  15 audit-core/audit-shard-08
│ │ │ ├─────────────────╯ │ │ │ │ │ │ │ │
│ │ │ │ │ │               ◆ │ │ │ │ │ │ │  16 audit-core/audit-shard-09
│ │ │ ├───────────────────╯ │ │ │ │ │ │ │
│ │ │ │ │ │                 ◆ │ │ │ │ │ │  17 audit-core/audit-shard-10
│ │ │ ├─────────────────────╯ │ │ │ │ │ │
│ │ │ │ │ │                   ◆ │ │ │ │ │  18 audit-core/audit-shard-11
│ │ │ ├───────────────────────╯ │ │ │ │ │
│ │ │ │ │ │                     ◆ │ │ │ │  19 audit-core/audit-shard-12
│ │ │ ├─────────────────────────╯ │ │ │ │
│ │ │ │ │ │                       ◆ │ │ │  20 audit-core/audit-shard-13
│ │ │ ├───────────────────────────╯ │ │ │
│ │ │ │ │ │                         ◆ │ │  21 audit-core/audit-shard-14
│ │ │ ├─────────────────────────────╯ │ │
│ │ │ │ │ │                           ◆ │  22 audit-core/audit-shard-15
│ │ │ ├───────────────────────────────╯ │
│ │ │ │ │ │                             ◆  23 audit-core/audit-shard-16
│ │ │ ├─────────────────────────────────╯
│ │ │ ○ │ │  07 audit-core/audit-shard-plan
│ │ ╭─┤ │ │
│ │ │ │ ◆ │  25 audit-core/audit-design
│ ╭─┬───╯ │
│ │ │ │   ◆  26 audit-core/audit-design-update
│ ╭─┬─────╯
│ │ ○ │  04 audit-core/audit-autochecks
│ ├─╯ │
│ │   ○  06 audit-core/audit-checks
│ │   ○  05 audit-core/audit-topics
│ ├───╯
│ ○  03 audit-core/ingest-input
│ ○  02 find-skill
├─╯
○  01 ingest-input

legend: ○ tool · ◆ agent · ▣ human · ↻ loop   │ all-dep · ╷ any-dep   when:/↻ inline
```

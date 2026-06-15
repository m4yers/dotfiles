# Plan Topology

Per-operation task DAGs rendered by loom. SKILL.md links here so the SKILL.md
body stays light at activation time.

## Contents

- [1. Create](#1-create)
- [2. Update](#2-update)
- [3. Review](#3-review)

## 1. Create

```text
○  24 summary-emit
▣  23 final-review
◆  22 skill-modify
○                    21 checks-report
├─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ ◆ ╷ ╷ ╷ ╷ ╷ ╷ ╷ ╷  12 check-authoring
├─╯ ╷ ╷ ╷ ╷ ╷ ╷ ╷ ╷
│   ◆ ╷ ╷ ╷ ╷ ╷ ╷ ╷  13 check-model-awareness
├───╯ ╷ ╷ ╷ ╷ ╷ ╷ ╷
│     ◆ ╷ ╷ ╷ ╷ ╷ ╷  14 check-scripts
├─────╯ ╷ ╷ ╷ ╷ ╷ ╷
│       ◆ ╷ ╷ ╷ ╷ ╷  15 check-secure-llm
├───────╯ ╷ ╷ ╷ ╷ ╷
│         ◆ ╷ ╷ ╷ ╷  16 check-interface   when: ${task:find-skill:type} == 'interface'
├─────────╯ ╷ ╷ ╷ ╷
│           ◆ ╷ ╷ ╷  17 check-tool   when: ${task:find-skill:type} == 'tool'
├───────────╯ ╷ ╷ ╷
│             ◆ ╷ ╷  18 check-workflow   when: ${task:find-skill:type} == 'workflow'
├─────────────╯ ╷ ╷
│               ◆ ╷  19 check-reference   when: ${task:find-skill:type} == 'reference'
├───────────────╯ ╷
│                 ◆  20 check-design
├─────────────────╯
○  11 check-autochecks
○  10 find-skill
◆  09 skill-materialize
↻      08 design-review   ↻ loop → design-author · while …
├─┬─╮
│ ○ │  06 design-render
├─╯ │
│   ○  07 design-checks
├───╯
◆      05 design-author
├─┬─╮
○ │ │  02 check-name
│ ○ │  03 check-location
├─╯ │
│   ○  04 check-overlaps
├───╯
▣  01 gather-create
```

## 2. Update

```text
○  20 summary-emit
▣  19 final-review
◆  18 skill-modify
○                    17 checks-report
├─┬─┬─┬─┬─┬─┬─┬─┬─╮
│ ◆ ╷ ╷ ╷ ╷ ╷ ╷ ╷ ╷  08 check-authoring
├─╯ ╷ ╷ ╷ ╷ ╷ ╷ ╷ ╷
│   ◆ ╷ ╷ ╷ ╷ ╷ ╷ ╷  09 check-model-awareness
├───╯ ╷ ╷ ╷ ╷ ╷ ╷ ╷
│     ◆ ╷ ╷ ╷ ╷ ╷ ╷  10 check-scripts
├─────╯ ╷ ╷ ╷ ╷ ╷ ╷
│       ◆ ╷ ╷ ╷ ╷ ╷  11 check-secure-llm
├───────╯ ╷ ╷ ╷ ╷ ╷
│         ◆ ╷ ╷ ╷ ╷  12 check-interface   when: ${task:gather-update:type} == 'interface'
├─────────╯ ╷ ╷ ╷ ╷
│           ◆ ╷ ╷ ╷  13 check-tool   when: ${task:gather-update:type} == 'tool'
├───────────╯ ╷ ╷ ╷
│             ◆ ╷ ╷  14 check-workflow   when: ${task:gather-update:type} == 'workflow'
├─────────────╯ ╷ ╷
│               ◆ ╷  15 check-reference   when: ${task:gather-update:type} == 'reference'
├───────────────╯ ╷
│                 ◆  16 check-design-update
├─────────────────╯
○  07 check-autochecks
◆  06 modify-changes
↻  05 design-review-update   ↻ loop → design-author-update · while …
○  04 design-render-update
◆  03 design-author-update
▣  02 gather-update
○  01 find-skill
```

## 3. Review

```text
○  15 review-finalize
↻  14 skill-fix-apply   ↻ loop → show-report · while …
▣  13 skill-fix-review
○  12 show-report
○                  11 checks-report
├─┬─┬─┬─┬─┬─┬─┬─╮
│ ◆ ╷ ╷ ╷ ╷ ╷ ╷ ╷  03 check-authoring
├─╯ ╷ ╷ ╷ ╷ ╷ ╷ ╷
│   ◆ ╷ ╷ ╷ ╷ ╷ ╷  04 check-model-awareness
├───╯ ╷ ╷ ╷ ╷ ╷ ╷
│     ◆ ╷ ╷ ╷ ╷ ╷  05 check-scripts
├─────╯ ╷ ╷ ╷ ╷ ╷
│       ◆ ╷ ╷ ╷ ╷  06 check-secure-llm
├───────╯ ╷ ╷ ╷ ╷
│         ◆ ╷ ╷ ╷  07 check-interface   when: ${task:find-skill:type} == 'interface'
├─────────╯ ╷ ╷ ╷
│           ◆ ╷ ╷  08 check-tool   when: ${task:find-skill:type} == 'tool'
├───────────╯ ╷ ╷
│             ◆ ╷  09 check-workflow   when: ${task:find-skill:type} == 'workflow'
├─────────────╯ ╷
│               ◆  10 check-reference   when: ${task:find-skill:type} == 'reference'
├───────────────╯
○  02 check-autochecks
○  01 find-skill
```

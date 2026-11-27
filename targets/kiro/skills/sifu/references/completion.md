# Completion Status

**Code:** CMP
**Applies:** always

Terminal states every skill reports. Supplements `authoring.md`.

## 1. Completion Status

1. (rule: CMP-1-1, severity: 80) Every skill MUST end with a `## Completion`
   section defining terminal states. (check:
   `autochecks/authoring.py:rule_6_1_completion_section`)

2. (rule: CMP-1-2, severity: 80) The section MUST use exactly four statuses:
   `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, `NEEDS_CONTEXT`. (check:
   `autochecks/authoring.py:rule_6_2_completion_statuses`)

3. (rule: CMP-1-3, severity: 80) `DONE_WITH_CONCERNS` MUST be used only for
   workflow-level problems (sub-agent returned empty, verification skipped
   because a tool was unavailable, partial failure tolerated) that warranted a
   retro but did not stop the workflow.

4. (rule: CMP-1-4, severity: 85) `DONE_WITH_CONCERNS` MUST NOT be used for
   outcome-level caveats the user consciously accepted (audit passed with
   overrides, user kept a flagged finding), because those belong in a clean
   `DONE` report.

5. (rule: CMP-1-5, severity: 80) The `DONE` row MUST state concrete evidence
   (e.g., "report saved", "drafts published"), not generic "task completed".

6. (rule: CMP-1-6, severity: 90) Skills involving iteration or investigation
   MUST include an escalation rule — e.g., "MUST stop after 3 failed attempts
   and report BLOCKED with what was tried".

```markdown
## Completion

| Status               | Criteria                            |
|----------------------|-------------------------------------|
| `DONE`               | Review report saved, drafts posted  |
| `DONE_WITH_CONCERNS` | Report saved, some files unreadable |
| `BLOCKED`            | CR checkout failed or no diff found |
| `NEEDS_CONTEXT`      | CR URL not provided                 |
```

"""Automated checks for ``references/flow-conventions.md``."""

from __future__ import annotations

from typing import List, Tuple

from sifu.autochecks._helpers import Finding, rule


@rule('FLW-2-2')
def rule_2_2_workflow_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """A flow skill MUST have a `## Workflow` section with steps.

    Rule: FLW-2-2
    """
    names = {(lvl, text.strip()) for _, lvl, text in headings}
    if (2, "Workflow") not in names:
        return [("SKILL.md", 0, "flow skill has no `## Workflow`")]
    if not any(lvl == 3 and text.startswith("Step")
               for _, lvl, text in headings):
        return [("SKILL.md", 0,
                 "flow `## Workflow` has no `### Step N` headings")]
    return []


@rule('FLW-2-3')
def rule_2_3_invariants_section(
    headings: List[Tuple[int, int, str]],
) -> List[Finding]:
    """A flow skill MUST have a `## Invariants` section.

    Rule: FLW-2-3
    """
    if any(lvl == 2 and text.strip() == "Invariants"
           for _, lvl, text in headings):
        return []
    return [("SKILL.md", 0,
             "flow skill has no `## Invariants` section")]

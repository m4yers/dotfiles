# Sub-Agent Query Template

Single template for all review sub-agents. Each sub-agent checks the skill
against one reference document.

```
Review the skill at {skill_dir} against the rules in
{reference_path}. Read the reference file and all skill
files (SKILL.md, references/, scripts/). If the reference
requires checking other skills (e.g. trigger uniqueness),
scan ~/.kiro/skills/**/SKILL.md frontmatter as needed.

Ultrathink about each rule before deciding whether it is
violated.

Return a list of violations as markdown, each with:
- title
- file:line
- description
- suggested fix
- severity (Error, Warning, or Info)

Return "None." if no violations found.

Exclude these lint false positives (already reported
by the automated linter): {lint_false_positives}
```

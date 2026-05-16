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

Return exactly ONE of these terminal markers on a line by
itself, OR a violations list — never empty output:

- `NO_FINDINGS` — analysis completed successfully, no
  violations found. This is a clean terminal result.
- `ERROR: <one-line reason>` — analysis could not be
  completed (could not read files, rule unclear,
  timeout, ambiguous scope). State the concrete reason.
  This is a failure; the caller will retry.

OR return a violations list as markdown, each with:
- title
- file:line
- description
- suggested fix
- severity (Error, Warning, or Info)

A violations list itself signals success — the number of
items is the finding count. Do not also include a
NO_FINDINGS or ERROR marker when returning a list.

Empty output or anything that is neither a violations
list nor begins with `NO_FINDINGS` / `ERROR:` is treated
as `ERROR: empty or malformed response` and retried.

Exclude these lint false positives (already reported
by the automated linter): {lint_false_positives}
```

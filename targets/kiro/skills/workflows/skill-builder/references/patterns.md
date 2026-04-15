# Skill Patterns

Reusable patterns for skill authors. Read when creating or
updating skills that match these scenarios.

## Circuit Breaker

Skills that iterate on output (query refinement, research,
drafting) SHOULD implement a three-attempt limit.

After three iterations that don't reach a usable state, stop
and offer alternatives:

```markdown
**Constraints:**
- You MUST stop iterating after 3 attempts that don't
  satisfy the user
- You MUST say: "I'm going in circles — want to take a
  different approach or handle it manually?"
- You MUST NOT continue refining without explicit user
  request to keep going
```

**When to apply:** iterative query tuning, vault searches
returning nothing, format/structure refinement.

**When NOT to apply:** one-shot operations (build, run test),
multi-step workflows where each step is distinct (RCA
investigating multiple domains isn't "iterating").

## Degrees of Freedom

Match instruction specificity to task fragility.

| Task type                    | Freedom | Skill pattern                              |
|------------------------------|---------|--------------------------------------------|
| Fragile (fleet sweep, vault  | Low     | Exact commands, validate before execution  |
| write, git push)             |         |                                            |
| Structured (RCA, tests)      | Medium  | SOP with constraints, allow adaptation     |
| Creative (research, review)  | High    | Goals and quality criteria, not steps      |

The test: if getting it wrong causes data loss or
embarrassment, constrain tightly. If getting it wrong just
means a suboptimal first draft, give freedom.

## Trigger Phrase Hygiene

When adding or updating a skill's description:

- Check other skill descriptions for overlapping trigger
  words
- Each skill SHOULD have at least 2-3 unique trigger
  phrases that no other skill claims
- If two skills share a trigger domain, make the routing
  criteria explicit in both descriptions
- Use negative triggers when scope overlaps: "Do NOT use
  for X (use Y skill instead)." Examples: debug-symbolize
  vs fast-debug, owls/fleet-sweep vs rca

## Instruction Effectiveness

- When the agent ignores a skill's instructions, the fix
  is usually to shorten them, not add more. Verbosity
  dilutes signal.
- Put critical constraints at the top of SKILL.md, not
  buried in later steps.
- For validations that must be deterministic (file format
  checks, schema validation), use a script instead of a
  language instruction. Code is deterministic; language
  interpretation isn't.

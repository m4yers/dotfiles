# No Reinvent

Before writing a new function, helper, type, constant,
script, or abstraction, search the codebase for
something that already does the job. Most projects
already have the utility you are about to write — under
a different name, in a neighboring module, or behind a
shared library. Reinventing it forks behavior, doubles
maintenance, and drifts from the project's conventions.

## Required before writing new code

For every non-trivial addition (helper, util, parser,
formatter, validator, wrapper, retry loop, path
resolver, config loader, cache, logger, error type, CLI
entry, test fixture, etc.), search first:

1. Search by intent — what the thing *does*. Use names
   the existing author would have picked: `parse_*`,
   `format_*`, `resolve_*`, `load_*`, `retry_*`,
   `with_*`, `find_*`.
2. Search by signature — argument types or return type
   if the language supports it.
3. Search adjacent modules and shared libraries —
   `util/`, `common/`, `lib/`, `helpers/`, the
   project's standard library equivalent.
4. Check imports of nearby files — they reveal the
   project's preferred utilities for this domain.
5. For Brazil/PADB workspaces, also search sibling
   packages that the current package already depends
   on.

If a match exists: use it, extend it, or refactor it.
Do not write a parallel implementation.

## Forbidden without a search

- Writing a new helper without grepping for existing
  ones with the same intent.
- Defining a new constant for a value that almost
  certainly has a name elsewhere (timeouts, magic
  paths, error codes, regex patterns, format strings).
- Adding a new error/exception type without checking
  the project's error hierarchy.
- Importing a third-party library for functionality
  that the project already wraps internally.
- Copy-pasting a snippet from another file instead of
  extracting and reusing it.

## When a near-match exists but is not exact

Prefer extending or generalizing the existing code over
forking it. Surface the choice to the user:

- "There is already `foo_helper` that does 80% of this.
  I can extend it with parameter `X`, or write a
  separate `bar_helper`. Extending keeps one source of
  truth; forking avoids touching shared code. Which?"

Only fork when extension is clearly worse (wrong
abstraction, breaks unrelated callers, crosses a module
boundary that should not be crossed). State the reason.

## What counts as a sufficient search

Not "I don't remember seeing one." A real search is:

- A grep / code-search across the repo for the intent
  keywords AND the likely signatures.
- A look at the obvious home directories for shared
  utilities.
- A glance at how nearby code solves the same problem.

If the search comes up empty after that, write the new
code — and place it where the next person will find it
on the same search.

## Why this rule is strict

Every duplicated helper is a fork in behavior. The two
copies drift, diverge in edge cases, and one of them
silently becomes wrong. Reviewers also bear the cost:
they must check whether the new code matches the
existing one, then ask why both exist. The cheapest
fix is to find the original first.

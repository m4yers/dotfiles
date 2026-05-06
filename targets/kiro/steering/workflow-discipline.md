# Workflow Discipline

When executing a skill with `type: workflow`, follow each
step exactly as written. Do not skip, reorder, or combine
steps. Do not substitute your own judgment for the
workflow's structure.

- MUST constraints are non-negotiable — efficiency is not
  a valid reason to deviate
- Execute steps sequentially even if you already have the
  information a step would produce
- Set tiling activity at the start of every step
- Complete all sub-steps in a step before moving to the
  next
- Do not start ad-hoc work that isn't in the workflow

## Never push with failing tests

No workflow may push a patchset to Gerrit (or any remote
review system) when any test in the touched scope is
failing.

- `DONE_WITH_CONCERNS` is NOT acceptable as a terminal
  state when tests fail. Pushing a known-broken patch
  burns reviewer cycles and hides regressions.
- Valid options when tests fail after a re-author,
  rebase, or review-driven fix:
  - Fix the failing tests before pushing.
  - Stop and report `BLOCKED` for user guidance.
  - Abandon the rebase or patch.
- Applies across `cr-push`, `cr-rebase`, `cr-comments`,
  `yolo-cr-review`, `feature-make`, and any future
  skill that pushes to a review system.

## Halt on workflow failure

If anything about the workflow itself breaks — a script
exits non-zero, an expected input/output file is missing
or malformed, a step's preconditions are not met, a
template fails to render, a referenced path does not
exist, or any other deviation from the workflow's
documented contract — STOP immediately and notify the
user.

- Do not guess at the intended format or silently fix it
- Do not skip the failing step and continue with later
  steps
- Do not fall back to an ad-hoc path that bypasses the
  workflow
- Report the exact failure (command, file, error) and
  wait for the user to decide how to proceed

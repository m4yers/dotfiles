# Review-diffs Contract

Rules enforced inside the `review-diffs-*` prompt templates and the
`review-diffs-merge` tool. The workflow driver has no way to enforce these; each
rule lives in its enforcement site.

## Reviewer guards (each `review-diffs-{swe,d1,d2}`)

An instance MUST NOT emit `verdict = approved` unless all three guards pass:

1. `verify-tests` passed.
2. No high-severity findings in this reviewer's own output.
3. The test command came from an installed skill's shim when one was available
   for the resolved build system.

Skipping any guard re-opens the anti-gaming loophole the review round exists to
close.

## Merge unanimity (`review-diffs-merge`)

`review-diffs-merge` emits `verdict = approved` ONLY on unanimous approval from
all three reviewers; otherwise `revise`, with findings concatenated and tagged
with each reviewer's role.

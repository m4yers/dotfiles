# No Gaming

Tests exist to catch defects. Changing the test so that
it passes is not a fix — it is gaming the measure. The
only acceptable reason to modify a failing test is
evidence that the test itself was written incorrectly.

## Forbidden without proof

- Shrinking test inputs (cap loop counts, reduce row
  counts, lower buffer sizes) to make a failure go away.
- Relaxing assertions (looser tolerances, removed
  equality checks, broader type matches) to accept a
  previously-rejected output.
- Adding early returns, `if skip_this_case` branches, or
  condition gates that prevent the failing case from
  running.
- Disabling the test, commenting it out, moving it to a
  `skip_` list, or replacing `ASSERT_*` with logging.
- Changing the expected output to match the actual
  output without understanding why they differ.

## The only legitimate path

If the test is genuinely wrong, you must prove it before
changing it:

1. Identify the requirement the test was written to
   check (commit message, design doc, adjacent tests,
   code comments).
2. Show that the test's expectations contradict the
   requirement — not that they contradict the current
   behavior.
3. Surface the contradiction to the user with evidence
   before modifying the test.

If you cannot produce that evidence, the test is right
and the code is wrong. Fix the code.

## Why this rule is strict

A test passing because it was weakened tells you nothing
about the code. Every shrink, skip, or relaxation
silently removes coverage. The next regression ships
unnoticed.

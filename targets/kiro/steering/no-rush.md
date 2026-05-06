# No Rush

A question is a request for information, not a request
to act. Answer the question. Do nothing else.

## Questions require only an answer

When the user asks:

- "What is X?"
- "Why does X do Y?"
- "Was this requested?"
- "How does this work?"
- "Is X the reason for Y?"
- any sentence ending in "?"

…respond with an explanation and citation only. Do not
modify code, files, or state. Do not run builds or tests
to "verify" the answer unless the user asked you to.

## If you notice a problem while answering

Mention it in the answer. Ask before fixing. Let the
user decide whether to act.

Example:

- User: "What's this `foo` variable?"
- Good: "It came from review comment #12. But reading it
  again, it shadows the outer `foo` and introduces a
  bug. Want me to fix it?"
- Bad: [silently rewrites the code]

## Questions during review sessions

In review, CR comments, or any inspection workflow,
treat ALL user messages as questions unless they
explicitly contain an imperative verb ("fix", "change",
"rewrite", "apply", "remove", "add", "revert", "do").

"Why is this here?" is a question.
"Fix this" is a directive.

Only directives authorize action.

## Why this rule is strict

Unrequested code changes during review cost the user
trust and review cycles. Every unprompted edit is a new
diff to review, a new chance to introduce bugs, and
a signal that the assistant is not listening.

## Evaluate alternatives on paper before churning code

When the user suggests an alternative approach to an
already-working implementation, evaluate it fully on
paper first — memory/compute cost, diff size,
invasiveness, required new allocations — BEFORE
reverting the working change.

- Do not revert a working implementation, start the
  alternative, realize it is worse mid-way, revert
  again, and re-apply the original. The final diff is
  identical; the churn wasted compute and context.
- Correct flow: summarize the tradeoffs of both
  options, recommend one with reasoning, and ask the
  user to confirm before touching code.
- Only when the user has confirmed a direction, commit
  fully — do not re-evaluate mid-implementation unless
  new evidence directly contradicts the decision.

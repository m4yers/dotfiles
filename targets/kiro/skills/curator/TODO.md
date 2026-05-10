# TODO

## Wire-in tiling and editor for review

## Summariser

1. Summariser is too simple. Needs to understand what is being summarised:
 - video/lecture
 - paper
 - book
 - etc

 2. Split summariser into several sub-scripts (?) per type + generic. Each
 summariser must be a pipeline:
  - Outline
  - Extend with details
  - Fix the language if needed

 3. Summariser must extract unspecified atomics, e.g  algos

 4. Another **judge** agents verifies the final summary for BS,
 against a rubric (TBD). If BS found the summariser re-does the work

 5. Maybe encyclopedic tone isn't the best.

## (NEW) Linker ?

Add an agent that takes the output of all other agents, traverses
the vault and tries to identify already present atomics/articles
and mark them as such.

Unless this is already done by the extractor. In any case existing
atomics/articles/concpets must be highlighted in the summary. This
matchng must be semantic, not just name-wise. Matching with confidence
level.

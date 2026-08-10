# Update: `curator` (workflow)

> Skill at `/home/artyomgo/.kiro/skills/home/curator` (namespace: `home`)

## Change request

Generalize curator's synthesis layer to support multiple "hub kinds" (wiki,
recipe, and future kinds), instead of always producing wiki pages plus all the
per-register/per-discipline noise.

Today the pipeline is:

- quintet rules add extractor kinds via additive union only.
- extract-synthesis ALWAYS runs and emits 21 WIKI/\* pages.
- destinations classifies each kind as `mode: artifact` (own page) or
  `mode: synthesis` (folded into wiki).
- For culinary sources this produces noise: forced `models` extractions and
  generic wiki pages alongside the recipe.

Required changes:

1. Introduce a third destination mode: `mode: hub`. A hub kind is the composed
   primary output for sources of a given type — synthesized from the source body
   plus peer extractor artifacts, mirroring the role wiki already plays. It is
   distinct from `mode: artifact` (per-item pages with no composer) and
   `mode: synthesis` (input kinds folded into a composed page): `hub` names the
   composed-output role that until now has been implicit and wiki-only.
   Examples:

   - recipes → hub for culinary sources (replaces wiki)
   - wiki → existing default hub (for sources that have no other hub kind) New
     hub kinds (e.g. interview-transcripts, code-projects) can be added later by
     tagging their kind `mode: hub` and writing a hub-specific composer
     template.

2. Skip the generic wiki composer when any hub-kind extractor has items. Make
   `extract-synthesis` (the wiki composer) gate on "no other hub fired". It
   still runs as the default hub when no kind-specific hub did.

3. Add a per-hub composer step. For each kind tagged `mode: hub`, emit a
   `compose-<kind>` agent task that runs after build-replica, reads the source
   body, the kind's extracted items, peer extractor outputs and judge verdicts
   (keywords, people, topics), and the replica directory, and re-synthesizes the
   kind's vault pages with:

   - inline first-occurrence wikilinks woven into prose fields,
   - a `## Key Concepts` section listing related entities,
   - optional `## Notes` / `## Discussion` sourced from peer extractors.
     Generalize, do not hard-code "recipes". The composer agent's prompt
     template lives at templates/prompts/`compose-<kind>.md.j2`; a base template
     handles common structure, kind-specific templates override sections.

4. Add quintet exclusions. Today rules are pure-additive. Add an `exclusions:`
   block parallel to `rules:` so a discipline can drop kinds that are noise for
   it. For culinary, exclude `models` (the forced "Method Over Product
   Principle" / "Render-and-Drain Stage Pattern" extractions are noise on a
   recipe). Other disciplines may exclude other kinds later.

5. Update the recipe template (templates/vault/recipe.j2) to render the new hub
   fields (`key_concepts`, discussion) the same way the wiki template does:
   `[[Name]] - summary` bullets under `## Key Concepts`, with an optional
   `## Notes` section. The description and step prose stay verbatim — the
   composer's wikilinks are pre-substituted into those strings before rendering.

6. Keep backward compatibility: sources that DON'T trigger a hub kind (papers,
   books, articles without recipes) still go through the existing wiki composer.
   The existing artifact-mode kinds (keywords, people, models when not excluded,
   etc.) keep producing their own atomic pages.

Out of scope for this update:

- Changing the extractor kind set itself (no new extractors).
- Changing the gate / replica / report flow.
- Reworking the `merge-<kind>` reconciliation step.

Constraints (keep the diff tight):

- DO NOT add abstractions or helpers beyond what the four changes above require.
- DO NOT refactor unrelated parts of plan.py / quintet.yaml.
- DO NOT introduce a new schema language; extend the existing destinations +
  rules YAML.

## Files affected

### Created

- **`templates/extractors/_meta/composer.j2`** — New base composer prompt that
  mirrors the `_meta/extractor.j2` + `_meta/judge.j2` layout: a `source_paths`
  block, an instructions block (default text), and a `builder_calls` block, each
  overrideable by the per-hub-kind composer.j2. _Keeps the per-kind composer
  templates terse — they only override the kind-specific instruction body and
  rendering protocol._
- **`templates/extractors/recipes/composer.j2`** — Recipe-specific composer that
  extends `_meta/composer.j2`: directs the agent to read recipe items + the
  replica directory + peer extractor judges, weave first-occurrence wikilinks
  into description and step prose, build `key_concepts` / notes / discussion
  lists, then re-render each recipe via templates/vault/recipe.j2 into the
  replica path.
- **`templates/prompts/compose-recipes.md.j2`** — New symlink to
  ../extractors/recipes/composer.j2 so the compose-recipes loom task resolves
  its prompt path the same way every other extract- and judge- task does.
- **`schemas/extractors/compose.yaml`** — Shared output schema for every
  `compose-<kind>` task: an object with a paths array of vault-relative .md
  paths the composer rewrote (mirrors the synthesis schema since both kinds emit
  the same envelope). _One shared schema avoids per-kind duplication; the path
  pattern is left open since each hub kind writes into its own folder._

### Modified

- **`scripts/curator/curator/quintet.yaml`** — Flip the recipes destination to
  mode: hub (folder unchanged); add an exclusions: block parallel to rules: so
  disciplines can subtract noise kinds, with the culinary-excludes-models entry
  as the first exclusion. _hub is the new third destination value the user
  introduced; exclusions: replaces the all-additive rule contract so culinary
  stops emitting forced models extractions._
- **`scripts/curator/curator/quintet.py`** — Subtract the matching exclusions:
  rules from the union returned by `extractors_for()`, and add a `hub_kinds()`
  accessor returning every destinations entry whose mode is hub. _plan.py
  iterates `hub_kinds()` to wire `compose-<kind>` tasks; predicates.py reuses
  the exclusion logic to gate per-kind extractors._
- **`scripts/curator/curator/predicates.py`** — Apply exclusions when compiling
  each per-kind JMESPath predicate so excluded kinds get an additional AND-NOT
  clause that suppresses them on the matching quintet patterns. _Without this
  the rules-only predicate keeps firing the extractor even when an exclusion
  targets the same quintet pattern._
- **`scripts/curator/curator/plan.py`** — Emit one `compose-<kind>` agent task
  per hub kind (after build-replica, after the kind judge), gate it with a
  when-predicate that skips when the kind extractor produced zero items, and
  gate extract-synthesis with a when-predicate that skips whenever any hub-kind
  extractor produced items. _Wiring composers and the synthesis gate is the
  central plan change; the gate predicates AND together one length-check per hub
  kind so future hubs add to the same boolean without code edits._
- **`scripts/curator/curator/vault/replica.py`** — Treat mode: hub like mode:
  artifact in `build_replica` — wipe the hub folder on rebuild and route
  hub-kind items through `_render_page_via_template` so each hub kind still
  produces atomic pages that `compose-<kind>` can rewrite later. _Without this
  build-replica skips the recipes folder wipe and atomic-page production, so
  compose-recipes would have nothing to overwrite._
- **`templates/vault/recipe.j2`** — Render an optional ## Key Concepts section
  as \[\[Name\]\] - summary bullets and an optional ## Notes / ## Discussion
  section, all guarded by is defined checks so the build-replica first-render
  with no `key_concepts` still passes. _description and step prose stay verbatim
  — compose-recipes pre-substitutes wikilinks into those strings and supplies
  the new top-level vars on its second render._
- **`scripts/curator/tests/test_plan.py`** — Add tests asserting that
  `compose-<kind>` tasks exist for every hub kind, depend on build-replica plus
  the kind judge, that extract-synthesis carries a when-predicate referencing
  every hub kind, and that the per-task task count matches the new total.
- **`scripts/curator/tests/test_predicates.py`** — Add tests asserting that
  adding a culinary-excludes-models exclusion produces a models predicate whose
  AND-NOT clause references discipline == culinary, and that excluding a kind
  under one quintet leaves other matching quintets unaffected.

### Deleted

_No removals._

## Open questions

The author wants confirmation on the following before materialization. Address
each in your review feedback if you choose `revise`.

- Should `wiki` be added as an explicit `mode: hub` entry in destinations, or
  kept implicit (with extract-synthesis treated specially as the default-hub
  fallback)? Recommendation: keep implicit, because wiki has no extractor
  template counterpart and adding it would force
  `discovery.list_extractor_kinds()` to invent a wiki kind.
- Should the shared compose-output schema live at
  schemas/extractors/compose.yaml (one schema for every `compose-<kind>`) or
  per-kind at schemas/extractors/`compose-<kind>.yaml`? Recommendation: shared,
  since every hub composer emits the same {paths: \[...\]} envelope as
  extract-synthesis.
- Should `compose-<kind>` declare explicit dependencies on judge-keywords /
  judge-people / judge-topics (so cascade-skip applies when those peers were
  skipped) or only on build-replica + `judge-<kind>` and read peer outputs by
  listing the replica directory? Recommendation: depend only on build-replica +
  `judge-<kind>` and read peers via the replica, mirroring extract-synthesis.
- Should extract-synthesis be skipped when any hub-kind extractor merely *ran*
  (its when-predicate was true), or only when a hub extractor *produced ≥1
  item*? The user wrote "when any hub-kind extractor has items"; the proposed
  predicate gates on item count > 0, so a culinary source that yields zero
  recipes still gets a wiki page. Confirm this is desired.
- Should exclusions: rows take the same \[media, form, register, discipline,
  audience\] match shape as rules: (full quintet pattern with wildcards), or a
  slimmer single-slot shape (e.g. discipline-only)? Recommendation: same shape
  as rules, because it costs nothing extra and keeps future audience- or
  form-targeted exclusions expressible.

## Rationale

The change moves the synthesis layer from a hard-coded wiki composer to a
per-hub-kind composer model. The three destination modes now name three distinct
roles: `artifact` produces per-item pages with no composer, `synthesis` marks
kinds that are inputs folded into a composed page, and `hub` marks kinds whose
vault pages ARE the composed primary output — synthesized from source body plus
peer artifacts. `hub` is not artifact-plus-decoration (the composer is
essential, not cosmetic) and not a `synthesis` variant (`synthesis` items have
no folder and no own pages — opposite role in the pipeline). quintet.yaml +
quintet.py + predicates.py expose the new mode and the exclusions vocabulary;
plan.py wires `compose-<kind>` tasks and gates extract-synthesis; replica.py
keeps producing atomic hub pages so `compose-<kind>` has something to rewrite;
recipe.j2 grows the optional sections the composer fills; the new
`_meta/composer.j2` + recipes/composer.j2

- prompts/compose-recipes.md.j2 + schemas/extractors/compose.yaml form the
  per-task surface; the two test files lock in the wiring and exclusion
  semantics. SKILL.md is intentionally not touched — the orchestrator workflow
  (drive loom, dispatch agent tasks, drive the human gate) is unchanged;
  `compose-<kind>` is just another agent task loom yields.

______________________________________________________________________

The canonical edit target is the design YAML at
`/tmp/dojo/update/curator/tasks/03-design-author-update/iter-00/output.yaml`.
Edits round-trip through the review gate — `accept` copies the (possibly
hand-tweaked) YAML into the gate output; `revise` loops back to
`design-author-update` with your free-text feedback.

# Design: Bounded Loops for Loom

Status: proposal
Scope: `loom` engine (`scripts/loom/loom/`)

## 1. Context

Loom is a passive, single-process **DAG** task executor. A skill declares a
static plan; loom validates it, lowers it to `plan.yaml`, schedules tasks,
runs `tool` tasks inline, renders prompts for `agent`/`human` tasks,
validates every output against a JSON Schema, and persists each state
transition atomically.

Today loom rejects every cycle. `validate/dag.py` runs a white/gray/black
DFS and raises `DAGError("cycle detected at task <id>")` before any disk
write. Iteration can only be faked by `loom.extend`, which appends a fresh
batch of *new* task ids each round — the loop control lives entirely in the
orchestrator, and there is no convergence test, counter, or reset.

This doc specifies the **minimal** change that lets loom express loops
natively while preserving the guarantees it exists to provide.

## 2. Problem

Loops require re-executing a node. Loom's state model is effectively
single-assignment:

- one task id → one directory `tasks/<NN-id>/` → one `output.yaml` → one
  terminal status;
- `done` is permanent; the scheduler (`engine/algorithm.py`) assumes a task
  reaches a terminal status exactly once and never leaves it.

A naive back-edge breaks this on three axes at once: it re-runs a `done`
task, overwrites its single output, and re-fires every downstream task. So
"add loops" is really "introduce **scoped, structured** non-monotonicity
without losing crash-resumability, and with every loop forced to declare a
way out".

## 3. Goals / Non-Goals

### Goals

- Express **single-entry / single-exit (SESE)** loops — the natural /
  reducible loop of compiler theory.
- Keep the **outer plan a DAG**: a loop region abstracts to one super-node,
  so all existing scheduling reasoning still applies outside it.
- Preserve **crash-resumability** (`resume()` recovers mid-loop), and
  require every loop to declare at least one exit condition. A static
  iteration cap is **not** treated as a real termination guarantee — see
  §6.1.
- Reuse the existing predicate, schema, render, and atomic-write machinery.

### Non-Goals

- Arbitrary / irreducible (multi-entry) cycles.
- Loops with no declared exit condition at all (neither `fuel` nor `while`).
- Failure-retry as the default loop behaviour (see §6, invariant 3).
- Parallel loop-body fan-out across iterations (future work).

## 4. The relaxation: reducible flow graphs only

The graphs we admit are exactly the **reducible flow graphs** of classical
compiler theory: a DAG plus **natural loops**, where every loop is a
single-entry / single-exit region — a **hammock** — that collapses to one
node. The standard names are used throughout (see the glossary, §12).

A hammock / SESE region has exactly one entry (the **header**) and one exit
(the **latch**), with a back-edge latch → header. Because it has a single
entry and single exit, the whole region behaves like one node in the
surrounding graph — that is the property that lets us keep DAG reasoning
everywhere else.

We allow a back-edge `n → h` **iff `h` dominates `n`** — the standard
**reducibility test**. The loop it induces is the **natural loop** of that
back-edge. Irreducible (multi-entry) loops stay rejected.

Minimal forms, smallest first:

| Level | Shape                         | Header≡Latch | Use case                       |
| ----- | ----------------------------- | ------------ | ------------------------------ |
| L1    | bounded self-loop (1 node)    | yes          | retry / single-output refine   |
| L2    | natural loop (body is a DAG)  | no           | review → fix → review feedback |

**Do-while (bottom test) is the chosen minimal form.** The loop decision is
itself a task output — the latch emits e.g. `{continue: bool}` — which fits
loom's "everything is a schema-validated `output.yaml`" model exactly. A
top-test `while` would need an extra pre-guard node able to skip the whole
region on iteration 0; do-while needs no new node.

### 4.1 Containment guarantee — the hammock (super-node) property

A loop region `R` (header `h`, latch `l`, body = the **natural loop** of the
back-edge `l → h`) is only admitted if it is a **hammock**: a subgraph that
provably **collapses to a single node** in the outer graph. "Collapses" has a precise meaning: every edge that crosses the
region boundary must touch `R` at exactly one of two ports — *enter through
`h`, leave through `l`* — and nothing else. If that holds, the outer graph
can replace all of `R` with one super-node `S` whose inbound edges are `h`'s
external dependencies and whose outbound edges are `l`'s external
dependents; the back-edge `l → h` becomes internal to `S` and the outer
graph stays a pure DAG. This is what "never escapes the loop" means
formally.

Edges here include **every** dependency *and* every data reference
(`${task:…}`, `${task_path:…}`, and `when:` predicates) — a reference is a
data edge and is policed identically. Let an edge `u → v` mean "`v` consumes
`u`" (`u` upstream). The admission invariants are:

- **C1 — single entry (header dominance).** For every cross-boundary edge
  `u → v` with `u ∉ R` and `v ∈ R`, it must be that `v = h`. Equivalently,
  no body node other than the header may depend on, or reference, anything
  outside `R`. This makes `h` dominate every node in `R`: you cannot reach
  an inner node without passing through the header.
- **C2 — single exit (latch post-dominance).** For every cross-boundary
  edge `u → v` with `u ∈ R` and `v ∉ R`, it must be that `u = l`.
  Equivalently, no outside task may depend on, or reference, any body node
  except the latch. This makes `l` post-dominate every node in `R`: every
  path out of the region passes through the latch.
- **C3 — reducibility / unique back-edge.** `l → h` is the *only* back-edge
  in `R`, and `h` dominates `l`. Any second back-edge, or a back-edge whose
  target is not dominated by its source, is rejected as irreducible.
- **C4 — body is structural and derived.** The region is *computed* as
  `{ x : h dominates x ∧ l post-dominates x }` from the back-edge
  `l → h` alone (the latch hosts the `latch:` block naming `h`; see §5.2).
  Nothing declares the body, so it cannot disagree with the graph — authors
  cannot draw a boundary the graph does not support, because they draw no
  boundary at all.
- **C5 — disjoint regions (nesting deferred).** Region bodies must be
  pairwise disjoint. Properly-nested regions are admissible in theory (they
  would form a **Program Structure Tree** of SESE regions), but nested-loop
  *execution* is not yet implemented — shared per-task round counters and
  fuel restoration are unsolved — so the validator currently rejects any two
  regions that share a node.

**Why this makes the reset safe (and the loop inescapable).** The reset in
§5.3 touches exactly `body ⊆ R`. By **C2**, no node outside `R` consumes any
inner node's output except `l`'s — and `l` is never reset — so resetting the
body cannot invalidate a single completed outer node. By **C1**, no inner
node consumes a *mutable* outer value mid-loop: every external input arrives
through `h`, from upstream tasks that are already `done` and stay `done`. So
re-running the body is well-defined and its effects are confined to `R`.
Containment is therefore not a convention the scheduler hopes holds at
runtime — it is a static precondition proven at admission (§5.5), so the
non-monotonic reset can never ripple outside the region.

## 5. Required changes

### 5.1 State model — per-iteration output namespacing

Version task state by iteration so each `(task, iteration)` is still
write-once (monotonic *within* an iteration):

```
tasks/<NN-id>/
├── iter-00/output.yaml
├── iter-01/output.yaml
└── ...
```

The task id stays stable. `${task:id}` resolves to the **current**
iteration's output. Per-iteration subdirectories exist **only** for tasks
inside a loop body; non-looping tasks keep today's flat
`tasks/<NN-id>/output.yaml` layout with no `iter-NN/` level at all.

Affected: `engine/store.py` (path computation `_numbered_name` →
`+ iter`), `engine/runner.py` (read/write current iteration).

### 5.2 plan.yaml — a `latch:` block on the latch task

Loop state lives on the **latch task** that owns the back-edge, not in a
separate section. The latch's own id is implicit; only the `header` is
named. The body is *not* stored — it is the natural loop of the back-edge
`latch → header`, derived at load (§5.5) and cached in the runtime. State is
written atomically like every other transition:

```yaml
- id: review
  kind: agent
  depends_on_all: [build]
  latch:
    header: fix                                   # back-edge: review → fix
    fuel: 5                                        # countdown; decremented each round, exit at 0
    while: "${task:review:verdict != 'approved'}" # exit when false
    # at least one of `fuel` / `while` is required; either alone is valid,
    # and both may be combined (loop stops as soon as either fires)
```

This removes the id duplication and the declared-vs-computed body mismatch
class entirely: with no `body:` to declare, the region is always exactly the
computed natural loop. `fuel` and `while` are **alternative exit controls** —
at least one must be present, either may be used alone, and both may be
combined. `resume()` reads the live `latch.fuel` so a crash mid-loop recovers
the right round; the round index for `iter-<k>/` namespacing is *derived*
from the count of iterations already performed (existing `iter-*` dirs), so
no second counter is stored — `fuel` is the only loop-control variable.

### 5.3 Scheduler — the reset transition

New transition `done → pending`, fired **only** by the latch, **only** for
nodes in the region (the cached natural loop). The latch continues iff
`(fuel absent ∨ fuel > 0) ∧ (while absent ∨ while == true)` — it stops as
soon as *either* control fires:

1. Latch completes, output validated as usual.
2. If continue: decrement `latch.fuel` (when present), reset every region
   node `done → pending`, leave everything outside the region untouched,
   loop again.
3. If stop (`fuel == 0` **or** `while` false): latch stays `done`, the
   region's single exit edge releases downstream tasks.

This is the one controlled non-monotonic step. It is scoped exactly to the
SESE region, so the rest of the graph never observes a node leaving a
terminal state. Lives in `engine/algorithm.py`.

### 5.4 Reference grammar — cross-iteration reads

A feedback loop must read the previous round. Add:

| Placeholder           | Resolves to                              |
| --------------------- | ---------------------------------------- |
| `${task:id@prev}`     | round before the latest completed one    |
| `${task:id@k}`        | a specific round `k` (absolute index)    |

`@`-prefixed selectors (not the ambiguous `:prev`) keep the iteration
selector distinct from a JMESPath field path; a path may still follow, e.g.
`${task:id@prev:val}`. `@prev` is the round before the latest completed
round, so it is meant for `while`/post-round use — during a round the latest
completed output already *is* the previous round.

Without this, a loop is blind retry, not convergence. Lives in
`engine/resolve.py` plus the `when:` desugaring.

### 5.5 Validator — reducible-only + exit condition required

`validate/dag.py` changes from "reject all cycles" to a loop-admission pass
that runs in static validation (init *and* extend), before any disk write,
and raises a `LoomPlanError` subclass on any violation:

1. **Find back-edges** via the existing white/gray/black DFS.
2. **Reducibility (C3).** For each back-edge `n → h`, require `h` dominates
   `n` — else `DAGError("irreducible loop")`. Require it be the only
   back-edge whose target is `h` — else `DAGError("multi-back-edge loop")`.
3. **Exit condition.** Require the `latch:` block to declare at least one of
   `fuel` / `while` — else `NoExitConditionError`. This only rejects a loop
   with *no* declared way out; it is deliberately **not** a termination
   proof (see §6.1).
4. **Compute the region (C4).** For each latch task `l` with a `latch:`
   block naming header `h`, build dominators (from roots) and
   post-dominators (from sinks) and set
   `R = {x : h dominates x ∧ l post-dominates x}`. The body is *derived*, not
   declared, so there is nothing to disagree with; the only check is that `R`
   is a valid hammock (single entry `h`, single exit `l` — verified by the
   boundary scan below).
5. **Boundary scan (C1/C2/C5).** Flatten every edge — `depends_on_*` plus
   every `${task:…}` / `${task_path:…}` / `when:` reference resolved to its
   target id — into one edge set, then check each edge that crosses the
   boundary of `R`:
   - inbound (`u ∉ R, v ∈ R`) with `v ≠ h` → `LoopEscapeError("entry not
     through header")`;
   - outbound (`u ∈ R, v ∉ R`) with `u ≠ l` → `LoopEscapeError("exit not
     through latch")`.
   For nested regions, require proper containment (one body ⊆ the other) —
   else `LoopNestingError`.
6. **Super-node check (interval reduction).** Collapse each admitted `R` to
   a single node and re-run ordinary DAG validation on the collapsed graph;
   it must be acyclic. This is **T1–T2 / interval reduction** applied to one
   region — the executable form of the §4.1 hammock guarantee.

`loom.extend` re-runs this entire pass on the merged graph, so no later
extension can add an edge that punches through a region boundary (an
`extend` that would do so fails validation and writes nothing — consistent
with §7's rule forbidding extension into a live region).

## 6. Invariants to preserve

1. **Liveness is operational, not static.** Every loop must declare at least
   one exit condition (`fuel` or `while`), which rejects the trivially-
   infinite loop. But a static cap is *not* a real safety guarantee:
   `fuel: 1_000_000_000` provably terminates yet would not end in our
   lifetime, so it is operationally identical to an unbounded loop. Genuine
   runaway protection is operational — a *sane* `fuel`, a convergence
   `while`, and a runtime wall-clock / token-cost budget enforced by the
   orchestrator (which loom surfaces but does not itself impose).
2. **Confined non-monotonicity.** Only the latch resets, only region nodes,
   only while an exit control still permits another round. Each iteration in
   isolation is a clean monotonic DAG. Confinement is *proven*, not assumed
   — see the containment guarantee (§4.1) and the admission checks that
   enforce it (§5.5).
3. **Failure still halts.** Restrict the back-edge to `done`-state
   convergence. A `failed` task still raises `RunAborted` and is *not*
   reset by the loop. Letting the loop revive a failed task turns it into a
   defect-masking retry. Retry-on-failure, if ever wanted, must be a
   separate, explicitly-annotated narrower kind.
4. **Atomicity / resumability.** `latch.fuel` is part of `plan.yaml` state;
   every decrement and reset is an atomic write.

## 7. Edge cases needing an explicit rule

- **`depends_on_any` fan-in across iterations** — must pin to the current
  iteration's outputs, otherwise "which round?" is ambiguous.
- **`loom.extend` into a live loop region** — forbid; ill-defined. Extension
  may only add tasks outside any loop region.
- **Nested loops** — not yet supported. The validator requires loop region
  bodies to be pairwise disjoint (a shared node raises `LoopNestingError`).
  Proper nesting is the intended future extension, blocked on per-region
  round counters and fuel restoration.
- **Reference from outside the loop to a looped task** — resolves to the
  final iteration's output (the value at exit).

## 8. Conceptual stop point

Loom already has two of Böhm–Jacopini's three structured primitives:
**sequence** (`depends_on`) and **selection** (`when:` / cascade-skip).
SESE loops add the third — **structured iteration** — completing structured
control flow *without* admitting `goto`-style irreducible graphs. That is
the principled boundary: reducible loops, single-entry/single-exit, a
required exit condition (`fuel` and/or `while`), per-iteration outputs.
Anything past it (multi-entry, exit-less, failure-retry-by-default) buys
little and costs the very
guarantees loom exists to provide.

## 9. Phased delivery

1. **L1 self-loop**: per-iteration namespacing + `fuel` countdown + reset
   for a single node + exit-condition check. Smallest blast radius; unblocks
   retry/refine.
2. **`${task:id@prev}` / `@k`** references — enables convergence.
3. **L2 natural loop**: SESE detection, dominator check, multi-node reset.
4. Edge-case rules (§7) + docs in `SKILL.md`.

## 10. Visualising a looped plan

`loom visualise` renders a plan as vertical box-drawn stages stacked along a
centerline rail, with `▼` edges between layers, status glyphs, and `[kind ]`
tags. Loops must extend this vocabulary with a **back-edge rail** drawn in
the left margin from the latch up to the header.

### 10.1 Today (no loops) — real `loom visualise` output

A feedback pipeline can only be drawn as a straight forward chain; the
review → fix relationship is invisible:

```
                ┌──────────────────────────────────────────┐
                │  PLAN                                    │
                │  ● 4 done · ◐ 1 running · ◇ 1 pending    │
                │  6 total                                 │
                └──────────────────────────────────────────┘

                ┌──────────────────────────────────────────┐
                │ ● 01  fetch                      [tool ] │
                └────────────────────┬─────────────────────┘
                                     ▼
                ┌──────────────────────────────────────────┐
                │ ● 02  summarise                  [agent] │
                └────────────────────┬─────────────────────┘
                                     ▼
                ┌──────────────────────────────────────────┐
                │ ● 03  fix                        [agent] │
                └────────────────────┬─────────────────────┘
                                     ▼
                ┌──────────────────────────────────────────┐
                │ ● 04  build                      [tool ] │
                └────────────────────┬─────────────────────┘
                                     ▼
                ┌──────────────────────────────────────────┐
                │ ◐ 05  review                     [agent] │  ← current
                │       when: ${task:review:verdict !=     │
                │       'approved'}                        │
                └────────────────────┬─────────────────────┘
                                     ▼
                ┌──────────────────────────────────────────┐
                │ ◇ 06  publish                    [tool ] │
                └────────────────────┬─────────────────────┘

Legend: ◇ pending · ▶ ready · ◐ running · ● done · ✗ failed · ⊘ skipped
```

### 10.2 Proposed — L2 natural loop (review → fix)

The latch (`review`) gains a second out-edge: `continue` follows the
left-margin back-edge up to the header (`fix`), `exit` drops to `publish`.
The header is `fix`; the loop body is `{fix, build, review}`. `fuel 3` shows
the remaining countdown; `fuel 5 → 0` is the authored budget. The latch exits
when `while` turns false **or** `fuel` reaches 0.

```
╭───▶┌──────────────────────────────────────────┐   ◀ loop header (entry)
│    │ ● 03  fix                        [agent] │
│    └────────────────────┬─────────────────────┘
│                         ▼
│    ┌──────────────────────────────────────────┐
│    │ ● 04  build                      [tool ] │
│    └────────────────────┬─────────────────────┘
│                         ▼
│    ┌──────────────────────────────────────────┐
│    │ ◐ 05  review              fuel 3 [agent] │   ◀ loop latch (exit test)
│    │       while: verdict != 'approved'       │
│    └───┬────────────────┬─────────────────────┘
│        │ continue       │
╰────────╯                ▼  exit: approved or fuel = 0
  fuel 5 → 0
     ┌──────────────────────────────────────────┐
     │ ◇ 06  publish                    [tool ] │
     └────────────────────┬─────────────────────┘
```

### 10.3 Proposed — L1 self-loop (header ≡ latch)

The minimal loop: one node retries/refines itself until converged or the cap
is hit. Body is the single node; the back-edge returns to the same box.

```
╭───▶┌──────────────────────────────────────────┐   ◀ self-loop (header ≡ latch)
│    │ ◐ 02  summarise           fuel 2 [agent] │
│    │       while: not converged               │
│    └───┬────────────────┬─────────────────────┘
│        │ continue       │
╰────────╯                ▼  exit: converged or fuel = 0
  fuel 3 → 0
     ┌──────────────────────────────────────────┐
     │ ◇ 03  emit                       [tool ] │
     └────────────────────┬─────────────────────┘
```

### 10.4 New visual vocabulary

Added to `visualise/glyphs.py` and the renderer; everything else is reused:

| Element        | Glyph          | Meaning                              |
| -------------- | -------------- | ------------------------------------ |
| back-edge rail | `│` `╭` `╰` `╯`| latch → header continue path         |
| entry arrow    | `╭───▶`        | back-edge re-enters the loop header  |
| latch fork     | two `┬` tees   | `continue` (left) vs `exit` (centre) |
| fuel tag       | `fuel k`       | remaining countdown on the latch     |
| exit caption   | `fuel n → 0`   | authored budget + the active exits   |

The renderer changes: `layout.py` must lay the loop body as a contiguous run
so the rail spans header→latch without crossing unrelated boxes, and
`render.py` draws the rail + fork. ASCII-only mode falls back to `|`, `+`,
`>`, `v` as the box table already does.

## 11. Alternatives rejected

- **Status quo (`loom.extend` unrolling)** — works for unbounded append but
  has no convergence test, no counter, no reset, and pushes all control into
  every orchestrator. Not a primitive.
- **Arbitrary back-edges** — breaks termination and DAG reasoning globally.
- **Top-test `while`** — needs an extra guard node for no real gain over
  do-while given loom's output-as-decision model.

## 12. Terminology

Standard graph / compiler theory terms used in this doc. They are the
precise names for the structures the design relies on; nothing here is loom-
specific except the mapping in the last column.

| Term                       | Definition                                                                                                                  | In loom                                  |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| **Flow graph**             | A directed graph with a distinguished entry; here, the task DAG plus loop back-edges.                                       | the lowered `plan.yaml` graph            |
| **Dominates**              | `a` dominates `b` if every path from entry to `b` passes through `a`.                                                       | basis of C1 (single entry)               |
| **Post-dominates**         | `b` post-dominates `a` if every path from `a` to a sink passes through `b`.                                                 | basis of C2 (single exit)                |
| **Back-edge**              | An edge `n → h` whose target `h` dominates its source `n`.                                                                   | the `latch → header` continue edge       |
| **Reducibility test**      | A back-edge is legal iff its target dominates its source; a graph is reducible iff all its back-edges satisfy this.          | C3; rejects irreducible (multi-entry) loops |
| **Reducible flow graph**   | A flow graph reducible to a single node by repeated T1–T2 transformations; equivalently, all back-edges are dominator edges. | the only graph class loom admits         |
| **Natural loop**           | For back-edge `n → h`: `{h}` plus all nodes that reach `n` without passing through `h`.                                      | the computed `body:` (C4)                |
| **Hammock**                | A subgraph with a single entry and single exit such that all external in-edges hit the entry and all external out-edges leave the exit. | a loop region `R` (C1 + C2)              |
| **SESE region**            | Single-Entry / Single-Exit region: an edge pair `(a,b)` with `a` dominating `b`, `b` post-dominating `a`, cycle-equivalent.  | the formal shape of a hammock            |
| **Program Structure Tree** | The hierarchy of canonical, properly-nested SESE regions of a flow graph (Johnson–Pearson–Pingali, 1994).                   | nesting rule C5                          |
| **T1–T2 / interval reduction** | Hecht–Ullman reductions: T1 deletes a self-loop, T2 merges a node into its unique predecessor; iterated, they collapse a reducible region to one node. | §5.5 step 6 super-node check             |
| **Header**                 | The single entry node of a natural loop / hammock; the back-edge target.                                                    | loop entry; reset destination            |
| **Latch**                  | The node holding the back-edge source; here also the exit / decision node.                                                  | emits `{continue}`; forks continue/exit  |
| **Reset**                  | (loom term) The `done → pending` transition applied to a body for the next iteration.                                        | §5.3; confined to `R` by the hammock property |
| **Fuel**                   | A countdown consumed once per round; the loop exits when it hits 0. Standard term in verified interpreters (EVM: *gas*; networking: *ttl*). A static cap, *not* a real termination guarantee (§6.1). | one of the two exit controls on a `latch:` block |

References: Aho/Lam/Sethi/Ullman *Compilers* (dominators, reducibility,
natural loops, intervals); Hecht & Ullman 1972 (T1–T2); Johnson, Pearson &
Pingali 1994 (Program Structure Tree / SESE); Ferrante, Ottenstein & Warren
1987 (hammocks in the PDG).

# Curator Page Types

Anatomy templates for keyword, person, model, and synthesis
pages. Also the report format used at Step 5 (user gate).

## Contents

- [Keyword Page](#keyword-page)
- [Person Page](#person-page)
- [Model Page](#model-page)
- [Synthesis Page](#synthesis-page)
- [Source Note](#source-note)

## Keyword Page

```markdown
---
type: keyword
aliases: [LoRA, Low-Rank Adaptation]
sources:
  - 10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf
last_updated: 2026-05-07
---

# LoRA (Low-Rank Adaptation)

One-paragraph definition in neutral encyclopedic voice.
State what it is, the class it belongs to, and what
problem it solves.

## How it works

Mechanism, equations, key parameters. Keep claims tied
to citations.

## Relation to other concepts

- [[Fine-Tuning]] — LoRA is a parameter-efficient variant.
- [[Adapter Modules]] — predecessor in the PEFT family.

## References

- [[10 SOURCES/Papers/2106.09685 - Hu et al - LoRA|Hu et al. 2021]]
```

Rules:
- First paragraph = definition.
- `## How it works` when mechanism exists; omit otherwise.
- `## Relation to other concepts` wikilinks only to pages
  that exist or will be created in the same ingest.
- `## References` last. Every body citation mirrored here.
- Target length: 150–500 words. Longer belongs in
  synthesis.

## Person Page

```markdown
---
type: person
aliases: []
affiliation: Microsoft Research
dates: 1990–
sources:
  - 10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf
last_updated: 2026-05-07
---

# Edward Hu

One-paragraph bio: role, field, notable contributions.
Stick to sources. No speculation about views or
personality.

## Known for

- [[LoRA]] — first author of the 2021 paper.
- Other work cited in sources.

## References

- [[10 SOURCES/Papers/2106.09685 - Hu et al - LoRA|Hu et al. 2021]]
```

Rules:
- Bio ≤ 5 sentences. Facts only.
- `## Known for` bullets link to keyword/model pages.
- Do not invent birth years, nationalities, or opinions
  not in a source.

## Model Page

```markdown
---
type: model
domain: probability
sources:
  - 10 SOURCES/Books/Algorithms to Live By - Christian & Griffiths.md
last_updated: 2026-05-07
---

# Gittins Index

One-paragraph definition: what the model computes, what
input it takes, what question it answers.

## Formulation

Formal definition, notation, key formulas.

## When it applies

Conditions under which the model is valid or useful.
Anti-patterns where it fails.

## Worked example

Short illustrative example if the source provides one.

## References

- [[10 SOURCES/Books/Algorithms to Live By - Christian & Griffiths|Christian & Griffiths 2016]]
```

Rules:
- Formulation in math when the source is formal; in prose
  when intuitive.
- Worked examples only if they fit in ≤ 10 lines.
- Target length: 200–800 words.

## Synthesis Page

```markdown
---
type: synthesis
topic: parameter-efficient-fine-tuning
covers:
  - 12 KEYWORDS/LoRA.md
  - 12 KEYWORDS/Adapter Modules.md
  - 12 KEYWORDS/Prefix Tuning.md
  - 13 PEOPLE/Edward Hu.md
sources:
  - 10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf
  - 10 SOURCES/Papers/1902.00751 - Houlsby - Adapters.pdf
last_updated: 2026-05-07
---

# Parameter-Efficient Fine-Tuning

Opening paragraph: the problem class and why it matters.
Frame the field, not the specific methods.

## Timeline

- 2019 — [[Adapter Modules]] (Houlsby) — insert bottleneck
  layers. First widely-cited PEFT method.
- 2021 — [[LoRA]] (Hu et al.) — rank decomposition, no
  inference overhead.
- 2021 — [[Prefix Tuning]] — tune prompts, not weights.

## Comparison

| Method    | Trainable params | Inference cost | Source            |
|-----------|------------------|----------------|-------------------|
| Adapters  | ~3 %             | Extra forward  | Houlsby 2019      |
| LoRA      | 0.01 %           | None (merged)  | Hu et al. 2021    |
| Prefix    | ~0.1 %           | Longer context | Li & Liang 2021   |

## Open questions

Short bullet list of debates or unresolved directions
across the covered sources. Speculation allowed if
clearly marked.

## References

- [[10 SOURCES/Papers/2106.09685 - Hu et al - LoRA|Hu et al. 2021]]
- [[10 SOURCES/Papers/1902.00751 - Houlsby - Adapters|Houlsby et al. 2019]]
```

Rules:
- Synthesis pages span ≥ 3 atomic pages. Fewer = promote
  content into the atomic page instead.
- `covers:` lists every atomic page the synthesis weaves.
  Use for Dataview queries and for the linter to detect
  orphans.
- Speculation is allowed in synthesis but must be clearly
  marked. Wikilinks where concepts exist.
- Target length: 500–2 000 words.

## Source Note

Written by the fetch/convert pipeline into
`10 SOURCES/<type>/<basename>.md`. For Papers and Books,
this is a short summary and pointer to the binary. For
Articles and Videos, this IS the source (full text or
transcript).

Paper / Book summary note:

```markdown
---
type: source
origin_url: https://arxiv.org/abs/2106.09685
fetched_at: 2026-05-07T22:48Z
last_updated: 2026-05-07
---

# 2106.09685 — Hu et al. — LoRA

**Authors:** Edward J. Hu, Yelong Shen, Phillip Wallis, …
**Year:** 2021
**Venue:** ICLR 2022

Three-paragraph summary in neutral voice. What the
source claims, what methods it uses, what it establishes.

## Related work cited

- [[1902.00751 - Houlsby - Adapters]]
- [[2101.00190 - Li & Liang - Prefix Tuning]]

See the full PDF at `2106.09685 - Hu et al - LoRA.pdf`
next to this note.
```

Article / Video body:

```markdown
---
type: source
origin_url: https://gist.github.com/karpathy/...
fetched_at: 2026-05-07T22:48Z
last_updated: 2026-05-07
---

# Karpathy — LLM Wiki

<full markdown body from trafilatura / yt-dlp transcript>
```


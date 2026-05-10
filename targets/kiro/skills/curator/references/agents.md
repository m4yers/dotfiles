# Curator Sub-Agents

Roster of sub-agents dispatched at Step 3 (extractors) and
Step 4 (composer).

## Contents

- [Extractor Roster](#extractor-roster)
- [Output Schemas](#output-schemas)
- [Composer](#composer)
- [Approval Schema](#approval-schema)
- [Adding an Extractor](#adding-an-extractor)

## Extractor Roster

Dispatched in parallel at Step 3. Each reads `source.md`
from the workdir, a slice of vault context, and writes a
JSON file back to the workdir.

| Agent              | Writes to           | Extracts                              |
|--------------------|---------------------|---------------------------------------|
| curator-summary    | `summary.json`      | 1–2 paragraph synthesis, key claims   |
| curator-sources    | `sources.json`      | books, papers, URLs referenced        |
| curator-keywords   | `keywords.json`     | atomic concepts                       |
| curator-people     | `people.json`       | individuals                           |
| curator-models     | `models.json`       | mental / formal models                |

Each extractor receives, in its prompt:
- `workdir` path
- Path to `source.md`
- Existing-names list for its type (from `engine.sh context`)
- Page-type anatomy (from `references/page-types.md`)
- Citation rules (from `references/schema.md` § Citation Rules)

## Output Schemas

### summary.json

```json
{
  "summary": "1-2 paragraph synthesis in neutral voice.",
  "key_claims": [
    "First major claim with embedded citation.",
    "Second major claim."
  ]
}
```

### sources.json

```json
{
  "referenced": [
    {
      "id": "src-1",
      "type": "paper",
      "title": "Parameter-Efficient Transfer Learning for NLP",
      "authors": ["Houlsby, N.", "Giurgiu, A."],
      "year": 2019,
      "arxiv": "1902.00751",
      "doi": null,
      "url": null,
      "mention_context": "Adapter modules, referenced throughout §2."
    },
    {
      "id": "src-2",
      "type": "book",
      "title": "Deep Learning",
      "authors": ["Goodfellow, I.", "Bengio, Y.", "Courville, A."],
      "year": 2016,
      "isbn": "9780262035613",
      "mention_context": "Cited for backprop fundamentals."
    },
    {
      "id": "src-3",
      "type": "url",
      "url": "https://github.com/microsoft/LoRA",
      "mention_context": "Reference implementation."
    }
  ]
}
```

Types: `paper`, `book`, `url`, `video`.

### keywords.json / people.json / models.json

Same shape, `items[].name` interpreted per folder.

```json
{
  "items": [
    {
      "id": "kw-1",
      "name": "LoRA",
      "match_existing": null,
      "action": "create",
      "rationale": "Core subject of paper; term not in vault.",
      "proposed_frontmatter": {
        "type": "keyword",
        "aliases": ["Low-Rank Adaptation"],
        "sources": ["10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf"],
        "last_updated": "2026-05-07"
      },
      "proposed_body": "## LoRA (Low-Rank Adaptation)\n\nFreezes pretrained weights..."
    },
    {
      "id": "kw-2",
      "name": "Fine-Tuning",
      "match_existing": "12 KEYWORDS/Fine-Tuning.md",
      "action": "extend",
      "rationale": "Existing page lacks parameter-efficient methods.",
      "proposed_section": "Related methods",
      "proposed_mode": "append",
      "proposed_body": "- **LoRA (2021)** — rank-decomposition injection. See [[LoRA]].",
      "proposed_frontmatter_delta": {
        "sources_add": ["10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf"],
        "last_updated": "2026-05-07"
      }
    }
  ]
}
```

Rules for extractors:
- `match_existing` MUST be set when the extracted name
  matches any existing name in the provided context list.
  Case-insensitive compare on the name; exact match on the
  alias list if present.
- `action` = `create` only when `match_existing` is `null`.
- `action` = `extend` requires `proposed_section` and
  `proposed_mode` (`append` / `replace`).
- `proposed_body` MUST cite the source via wikilink at
  least once.
- `id` pattern per type: `kw-N`, `p-N`, `m-N`, `src-N`.

## Composer

`curator-composer` reads all five extractor JSON files plus
the vault context, reconciles duplicates one last time, and
writes `composed.json`.

### composed.json

```json
{
  "source": {
    "path": "10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf",
    "basename": "2106.09685 - Hu et al - LoRA",
    "type": "pdf"
  },
  "summary": "...",
  "proposals": {
    "keywords":  [ /* items, reconciled */ ],
    "people":    [ ... ],
    "models":    [ ... ],
    "synthesis": [
      {
        "id": "syn-1",
        "path": "21 SYNTHESIS/Parameter-Efficient Fine-Tuning.md",
        "action": "create",
        "rationale": "Weaves LoRA + Adapter Modules + Prefix Tuning.",
        "proposed_frontmatter": {
          "type": "synthesis",
          "topic": "parameter-efficient-fine-tuning",
          "covers": [
            "12 KEYWORDS/LoRA.md",
            "12 KEYWORDS/Adapter Modules.md"
          ],
          "sources": ["10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf"],
          "last_updated": "2026-05-07"
        },
        "proposed_body": "..."
      }
    ]
  },
  "related_sources": [
    {
      "type": "paper",
      "title": "Adapter Modules",
      "authors": ["Houlsby"],
      "year": 2019,
      "arxiv": "1902.00751",
      "reason": "Direct PEFT predecessor, referenced throughout."
    }
  ]
}
```

Composer rules:
- Every `proposals.synthesis[].covers` MUST list atomic
  pages either already existing in context OR proposed in
  `proposals.{keywords,people,models}`.
- Synthesis is proposed when the source introduces ≥ 3
  new or extended atomics connected by a common topic.
- `related_sources` is a filtered subset of
  `sources.json.referenced` — drop items already in
  `10 SOURCES/`, keep the ≤ 10 most relevant.

## Approval Schema

Written by the orchestrator after the user gate (Step 5).

### approved.json

```json
{
  "workdir": "/tmp/curator/2026-05-07/2106-09685-hu-et-al-lora",
  "decisions": [
    { "id": "kw-1",  "action": "approve" },
    { "id": "kw-2",  "action": "edit", "override_body": "..." },
    { "id": "p-1",   "action": "deny" },
    { "id": "syn-1", "action": "approve", "override_path": "21 SYNTHESIS/PEFT.md" }
  ]
}
```

Actions:
- `approve` — apply as composed
- `edit` — override one or more fields; fields are
  `override_body`, `override_frontmatter`,
  `override_section`, `override_mode`
- `deny` — skip
- `rename` — change the name (also changes the target path)
- `redirect` — merge into an existing page instead. Target
  specified as `override_path`. Mode becomes `extend`.

## Adding an Extractor

To add a new extractor (e.g., `curator-events`):

1. Create `~/dotfiles/targets/kiro/agents/curator-events.json`
   using one of the existing agents as a template.
2. Add a row to the Extractor Roster table above.
3. Define its output schema in this file.
4. Add a folder for its atomic pages
   (e.g., `15 EVENTS/` in the vault).
5. Update `engine.sh context` to include the existing-names
   list for that type.
6. Update SKILL.md Step 3 to dispatch the new extractor in
   parallel with the others.
7. Update `curator-composer` prompt to accept the new input
   file and reconcile against existing events.

No engine.py code changes are required for core commands —
only the context provider needs the new type.

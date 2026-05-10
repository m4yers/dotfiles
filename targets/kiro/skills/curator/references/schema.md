# Curator Schema

Folder roles, scope rules, citation rules, and frontmatter
specification for `~/Obsidian/MahVault/`.

## Contents

- [Vault Layout](#vault-layout)
- [Ownership and Scope](#ownership-and-scope)
- [Source Layout](#source-layout)
- [Link Direction](#link-direction)
- [Frontmatter Spec](#frontmatter-spec)
- [Citation Rules](#citation-rules)
- [File Naming](#file-naming)
- [Lint Categories](#lint-categories)

## Vault Layout

```
~/Obsidian/MahVault/
├── 10 SOURCES/           raw + source notes
│   ├── Papers/
│   ├── Books/
│   ├── Articles/
│   └── Videos/
├── 11 QUOTES/            human-extracted quotes (read-only)
├── 12 KEYWORDS/          atomic concept pages (llm)
├── 13 PEOPLE/            atomic entity pages (llm)
├── 14 MODELS/            atomic model pages (llm)
├── 20 ZETTELKASTEN/      permanent zettels (read-only)
├── 21 SYNTHESIS/         llm-authored synthesis + index (llm)
├── 30 PROJECTS/          active / creative work (read-only)
└── 60 MNEMONICS/         personal mnemonics (read-only)
```

Rows 11–14 are the atomic-extraction layer: one concept per
page. Rows 20–21 are the free-form layer (essays, syntheses).
Row 10 is the source of truth.

## Ownership and Scope

| Folder                  | Mode        | Who writes          |
|-------------------------|-------------|---------------------|
| `00 MEDIA` (deprecated) | read-only   | migrated / retired  |
| `10 SOURCES/Papers/*`   | pdf: ro     | binary immutable    |
| `10 SOURCES/Papers/*.md`| writable    | curator             |
| `10 SOURCES/Books/*.md` | writable    | curator             |
| `10 SOURCES/Books/*.pdf`| read-only   | binary immutable    |
| `10 SOURCES/Articles/*` | writable    | curator             |
| `10 SOURCES/Videos/*`   | writable    | curator             |
| `11 QUOTES/`            | read-only   | you                 |
| `12 KEYWORDS/`          | writable    | curator             |
| `13 PEOPLE/`            | writable    | curator             |
| `14 MODELS/`            | writable    | curator             |
| `20 ZETTELKASTEN/`      | read-only   | you                 |
| `21 SYNTHESIS/`         | writable    | curator             |
| `30 PROJECTS/`          | read-only   | you                 |
| `60 MNEMONICS/`         | read-only   | you                 |
| `*.assets/`             | read-only   | managed by writer   |

The curator's write path list is enforced by
`engine.sh page write` — writes outside this list fail.

## Source Layout

Every source under `10 SOURCES/<type>/` has a stable basename.
All artifacts — binary, note, media — share that basename so
Obsidian displays them adjacent and wikilinks resolve.

```
10 SOURCES/Papers/
  1999 Giappaolo - Practical File System Design.pdf
  1999 Giappaolo - Practical File System Design.md       ← summary note
  1999 Giappaolo - Practical File System Design.assets/  ← optional media

10 SOURCES/Books/
  Bullshit Jobs - David Graeber.md     ← reference note (book DB or curator)
  Bullshit Jobs - David Graeber.pdf    ← added when full text ingested
  Bullshit Jobs - David Graeber.epub   ← optional
  Bullshit Jobs - David Graeber.assets/

10 SOURCES/Articles/
  Karpathy - LLM Wiki.md               ← trafilatura output
  Karpathy - LLM Wiki.assets/
    img-1.png

10 SOURCES/Videos/
  Channel - Title.md                    ← transcript + summary
  Channel - Title.assets/
    thumbnail.jpg
```

Basename rule: `<primary-author-or-channel> - <title>` or for
papers `<year> <authors> - <title>`, lightly slugified (replace
`/` with `—`, strip control chars). The curator enforces this
in `engine.sh fetch`.

## Link Direction

Links flow from derived toward raw. Never the other way.

```
21 SYNTHESIS  ─→  12 / 13 / 14  ─→  10 SOURCES
                                     ↑
20 ZETTELKASTEN  ────────────────────┘
                 ─→  12 / 13 / 14
```

- `10 SOURCES/` notes never link back to atomic pages. The
  curator does not append "Referenced by" sections. The
  graph view and Obsidian's backlinks pane already surface
  reverse links without polluting the source note.

- `11 QUOTES/` notes may link to atomic pages when you write
  them; the curator never edits existing quotes.

- `20 ZETTELKASTEN/` notes may link to atomic pages; the
  curator may *propose* (via lint) but never apply.

## Frontmatter Spec

All curator-written pages carry frontmatter. Minimum schema:

```yaml
---
type: keyword | person | model | synthesis | source
sources:
  - 10 SOURCES/Papers/<basename>.pdf
  - 10 SOURCES/Books/<basename>.md
last_updated: 2026-05-07
---
```

Type-specific additions:

| Type       | Extra fields                                   |
|------------|------------------------------------------------|
| `keyword`  | `aliases: [...]` (optional)                    |
| `person`   | `aliases: [...]`, `affiliation:`, `dates:`     |
| `model`    | `domain:` (e.g. probability, economics)        |
| `synthesis`| `topic:`, `covers: [12/..., 13/..., 14/...]`  |
| `source`   | `origin_url:`, `fetched_at:`                   |

All fields optional except `type`, `sources`, and
`last_updated`. Omit `sources` only for `source` type notes
where the source *is* the page itself.

## Citation Rules

1. Every factual claim on an LLM-written page MUST cite at
   least one `10 SOURCES/` or `11 QUOTES/` path.
2. Citation format: wikilink to the source file.
   ```markdown
   LoRA reduces trainable parameters by 10 000× compared
   to full fine-tuning ([[10 SOURCES/Papers/2106.09685 - LoRA|Hu et al. 2021]]).
   ```
3. Page-bottom `## References` section lists every source
   cited in the body, in wikilink form.
4. The curator MUST NOT introduce claims not present in the
   cited source. Speculation, context, and analogies go in
   synthesis pages and must be clearly marked (e.g.,
   "*Note: not in source — inferred connection to …*").
5. Uncited pages are rejected by `engine.sh page write`
   unless passed `--allow-uncited` (only used for stubs
   created as placeholders).

## File Naming

- Page name = concept/person/model name, no folder prefix in
  the filename.
- Collisions: append `(<disambig>)` in parentheses. Example:
  `CMOS (Complementary Metal-Oxide).md` vs
  `CMOS (Charge-Coupled Device).md`.
- Curator normalizes: trims whitespace, collapses multiple
  spaces, converts `/` to `—`, strips trailing punctuation.
- Preserve the user's existing capitalization conventions:
  proper nouns capitalized, concepts title-cased except
  articles/conjunctions.

## Lint Categories

`engine.sh lint` returns health findings grouped into the categories below.
Each category is an array of items the user may act on manually; the curator
never applies lint-proposed fixes without explicit approval.

| Category    | What it flags                                   |
|-------------|-------------------------------------------------|
| `stubs`     | Writable pages with <50 chars of body content   |
| `orphans`   | Atomic pages not linked from any other page     |
| `misfiled`  | Pages whose folder does not match their `type`  |
| `uncited`   | Pages missing `sources:` and source wikilinks   |
| `stale`     | Pages whose `last_updated` is older than the    |
|             | oldest cited source's `fetched_at`              |
| `transient` | Leftover workdirs under `/tmp/curator/<date>/`  |

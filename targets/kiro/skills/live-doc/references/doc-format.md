# Live-doc format

A live doc is a vault markdown file with four H1 sections in a fixed order:

1. **Free-form intro** (before the first H1): one or two sentences
   naming the authoritative external source (e.g. a Quip board URL).
2. **`# Instructions`** — the human-readable task description, split
   into three fixed H2 subsections:
   - `## Data ingestion`
   - `## Data inference`
   - `## Data presentation`

   Instructions MAY reference external sources (Quip, SIM, wikis) and
   may be terse. They are the input the stage agents read.
3. **`# Result`** — refresh output: a `Last refresh: <UTC ts>` line,
   a one-paragraph summary with row counts and deltas against the
   previous refresh, then one `## <heading>` subsection per
   presentation instruction (mostly stdout verbatim).
4. **`# Appendix`** — the three fixed H2 subsections mirror the ones
   under `# Instructions`. Each stage subsection contains a numbered
   run order, then one `### <script-name>` block per script with a
   brief description capturing non-encodable assumptions, followed
   by the full script in a fenced code block.

## Three-stage shape

The three H2 subsections under `# Instructions` and `# Appendix` MUST appear
in the order shown and MUST NOT be renamed, reordered, or duplicated because
the parser raises `BadDocShapeError` on any deviation and refuses to run the
pipeline.

Docs that need inference AFTER presentation, or a second inference pass, cannot
be expressed in this shape and MUST be split into multiple live docs. Design
intent: the fixed shape removes a plan-scripts agent task and one failure mode
by making stage order a parse-time property rather than a runtime decision.

## Round-trip contract

The Appendix is the source of truth for scripts. On refresh:

- `load-doc` parses the current Appendix into stage-grouped
  `ScriptEntry` objects.
- Stage agents keep or regenerate scripts prudently and emit the
  final set via `$LOOM output add`.
- `assemble-doc` writes the entire doc back from the stage outputs,
  laying the Appendix out as three H2 stage subsections (run-order
  list + per-script H3 description + fenced source).
- `verify-roundtrip` re-parses the written doc and asserts
  stage-grouped script hashes and result subsection headings match;
  divergence fails before `commit-vault` runs.

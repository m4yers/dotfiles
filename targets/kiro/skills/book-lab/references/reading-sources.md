# Reading a chapter and proposing examples

How to read a requested chapter from each kind of book source, then turn it into
a brief summary and a menu of candidate coding examples the user can pick from.

## Contents

- [1. Locate the chapter](#1-locate-the-chapter)
- [2. Git repo or directory source](#2-git-repo-or-directory-source)
- [3. PDF source](#3-pdf-source)
- [4. EPUB source](#4-epub-source)
- [5. Summarise the chapter](#5-summarise-the-chapter)
- [6. Shape the example menu](#6-shape-the-example-menu)

## 1. Locate the chapter

1. The source kind is inferred from `BL_BOOK`: a directory or
   `.git` repo, a `.pdf`, or a `.epub`.
2. Extract only the requested chapter's text, not the whole
   book, because the summary MUST be grounded in the chapter the
   user asked for.

## 2. Git repo or directory source

1. List the tree and read the files that make up the chapter
   (markdown, LaTeX, or source) directly with the read tools.
2. When the chapter spans several files, read them in document
   order before summarising.

## 3. PDF source

1. Prefer `pdftotext` when available, because it is fast and has
   no dependency setup:
   ```bash
   pdftotext -f <first-page> -l <last-page> "$BL_BOOK" - | less
   ```
2. When `pdftotext` is absent, run a one-off via uv so no venv is
   installed:
   ```bash
   uv run --with pypdf python -c 'import sys,pypdf; r=pypdf.PdfReader(sys.argv[1]); print("\n".join(p.extract_text() for p in r.pages[int(sys.argv[2]):int(sys.argv[3])]))' "$BL_BOOK" <start> <end>
   ```
3. Find the page range from the table of contents or the PDF
   outline first; ask the user for the range when the outline is
   missing, because guessing the span wastes extraction passes.

## 4. EPUB source

1. An EPUB is a zip of XHTML files. List the entries and read the
   chapter's XHTML:
   ```bash
   unzip -l "$BL_BOOK"
   unzip -p "$BL_BOOK" "OEBPS/<chapter-file>.xhtml"
   ```
2. Read `toc.ncx` or `nav.xhtml` to map chapter titles to their
   XHTML files.

## 5. Summarise the chapter

1. Keep the summary brief — a few sentences on the chapter's core
   idea, plus the key formulas, models, or claims it introduces.
2. Ground every statement in the extracted text; do not import
   outside knowledge or invent results the chapter does not make,
   because the user relies on the summary to match their reading.

## 6. Shape the example menu

1. Offer a numbered list of candidate experiments, each a
   one-line idea tied to a specific concept, figure, table, or
   exercise in the chapter.
2. Favour ideas that compute or simulate something tweakable, so
   each maps cleanly onto one `argparse`-driven script.
3. Keep each idea to a single experiment; a broad idea SHOULD be
   split into separate numbered entries so the user picks at the
   granularity of one file.

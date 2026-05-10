# Curator Handlers

Per-URL-type ingestion recipes invoked by `engine.sh fetch`.
Each handler is a module under `scripts/engine/handlers/`.
This document describes what each produces and where.

## Contents

- [Dispatch](#dispatch)
- [pdf](#pdf)
- [youtube](#youtube)
- [html](#html)
- [local](#local)

## Dispatch

`engine.sh fetch <url-or-path>` routes based on URL shape:

| Pattern                                         | Handler   |
|-------------------------------------------------|-----------|
| `youtube.com/watch` / `youtu.be/`               | youtube   |
| `*.pdf` URL                                     | pdf       |
| `arxiv.org/abs/<id>` / `arxiv.org/pdf/<id>.pdf` | pdf       |
| HTML article URL                                | html      |
| `gist.github.com/<user>/<id>`                   | html      |
| `raw.githubusercontent.com/.../*.md`            | html      |
| local path (existing file on disk)              | local     |

Dispatch returns JSON:
```json
{
  "path":     "10 SOURCES/Papers/2106.09685 - Hu et al - LoRA.pdf",
  "type":     "pdf",
  "basename": "2106.09685 - Hu et al - LoRA",
  "workdir":  "/tmp/curator/2026-05-07/2106-09685-hu-et-al-lora"
}
```

`path` is vault-relative (under `~/Obsidian/MahVault/`).
`workdir` is the per-ingest scratch dir for sub-agents.

## pdf

Downloads the PDF to `10 SOURCES/Papers/<basename>.pdf`.
For arxiv URLs, derives the stable filename from the
abstract page (authors, title, year). Extracts text to
`<workdir>/source.md` at the convert step.

Deps: `httpx` (download), `pypdf` (text extraction).

Behavior:
- Arxiv: fetch `/abs/<id>`, scrape title + authors, compose
  basename as `<id> - <first-author-et-al> - <short-title>`.
- Direct PDF URL: derive basename from Content-Disposition
  header if present, else from URL path, else from the PDF
  metadata title.
- If a file with the target basename already exists, append
  ` (2)` etc. Never overwrite.
- Compute SHA-256 of the downloaded file and record in
  `<workdir>/meta.json` for de-dup hints.

## youtube

Fetches the transcript via `yt-dlp` (captions, auto-subs as
fallback), saves as `10 SOURCES/Videos/<basename>.md`.

Deps: `yt-dlp`.

Behavior:
- Basename: `<channel> - <title>` (slugified).
- Frontmatter: `origin_url`, `fetched_at`, `duration`,
  `uploaded`, `channel`.
- Body: transcript with `[MM:SS]` timestamp anchors every
  ~30 seconds so atomic pages and synthesis can cite
  specific moments.
- If no subtitles and no auto-subs: fail loudly. No
  transcription fallback in v1.
- Thumbnail saved to `<basename>.assets/thumbnail.jpg`.

## html

Fetches HTML, runs `trafilatura` in markdown mode, saves to
`10 SOURCES/Articles/<basename>.md`. Downloads inline images
to `<basename>.assets/`.

Deps: `httpx`, `trafilatura`.

Behavior:
- Basename: `<author-or-site> - <title>`. Falls back to the
  `<title>` tag; if absent, uses a slug of the URL.
- Image pipeline:
  1. `trafilatura` produces markdown with remote `<img>`
     URLs preserved.
  2. A post-processor walks the markdown for image refs,
     downloads each to `<basename>.assets/img-<n>.<ext>`,
     rewrites the markdown path to the local sibling.
  3. Any image fetch that fails leaves the remote URL
     in place and logs a warning to `<workdir>/fetch.log`.
- Frontmatter: `origin_url`, `fetched_at`, `author` (if
  trafilatura extracted), `published_date`.
- For YouTube URLs embedded in HTML articles: no recursion —
  flagged to the user at Step 6 as potential follow-up
  ingests.

## local

For files already on disk, either inside `~/Obsidian/MahVault/
10 SOURCES/` (no copy) or elsewhere (copied into the right
`<type>/` subfolder based on extension).

Behavior:
- `.pdf` / `.epub` → `10 SOURCES/Papers/` or
  `10 SOURCES/Books/` (asks user if extension is `.pdf` and
  the file lives outside either folder).
- `.md` → `10 SOURCES/Articles/` unless basename matches an
  existing book note (fuzzy, asks confirmation).
- Other text → refuses. Convert by hand first.
- Files already inside `10 SOURCES/` are left in place; only
  basename normalization is applied (with confirmation if
  the filename changes).

"""PDF handler — generic + arxiv specialization.

Arxiv URLs are resolved through the arxiv API to derive a stable
``<id> - <author> - <short title>`` basename. Every other PDF is
downloaded as-is with a basename derived from the URL.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import arxiv
import httpx

from curator import vault
from curator.source.config import (
    ARXIV_SHORT_TITLE_MAX,
    HTTP_TIMEOUT_PDF,
)
from curator.source.errors import (
    HandlerError,
    HandlerErrorCode,
    reused_envelope,
    safe_handler,
)


PAPERS_DIR = f"{vault.SOURCES_DIR}/Papers"


@safe_handler("pdf")
def handle_pdf(url: str, wd: Path) -> dict:
    """Download PDF, compute stable basename, write meta."""
    parsed = urlparse(url)
    is_arxiv = (parsed.netloc == "arxiv.org"
                and (parsed.path.startswith("/abs/")
                     or parsed.path.startswith("/pdf/")))

    if is_arxiv:
        basename, pdf_url = _resolve_arxiv(url)
    else:
        pdf_url = url
        basename = _basename_from_url(url)

    basename = vault.slugify_basename(basename)
    dest_rel, _exists = _pdf_dest(basename)
    if _exists:
        return reused_envelope(dest_rel, "paper", basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    with httpx.stream(
        "GET",
        pdf_url,
        follow_redirects=True,
        timeout=HTTP_TIMEOUT_PDF,
        headers={"User-Agent": "curator/0.1"},
    ) as r:
        r.raise_for_status()
        with open(dest_abs, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)

    # Record meta.
    meta = {"origin_url": url, "resolved_pdf_url": pdf_url,
            "size_bytes": dest_abs.stat().st_size}
    (wd / "meta.json").write_text(json.dumps(meta, indent=2))

    return {
        "path":         dest_rel,
        "type":         "pdf",
        "content_type": "paper",
        "basename":     basename,
    }


def _resolve_arxiv(url: str) -> tuple[str, str]:
    """Return (basename, pdf_url) for an arxiv /abs/ or /pdf/ URL.

    Basename shape: ``<id> - <first-author-et-al> - <short-title>``.
    Falls back to just the arxiv id if the metadata lookup fails
    (API rate limit, transient network error, etc.).

    Uses the ``arxiv`` Python library, which wraps the official
    arxiv API — more robust than scraping the abstract page's meta
    tags and respects arxiv's rate-limit guidance automatically.
    """
    m = re.search(r"arxiv\.org/(abs|pdf)/([\d\.]+)", url)
    if not m:
        raise HandlerError(
            HandlerErrorCode.PARSE_ERROR,
            f"unparseable arxiv url: {url}",
            {"url": url},
        )
    arxiv_id = m.group(2).rstrip(".pdf")
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    basename = arxiv_id  # fallback when the API lookup fails
    try:
        search = arxiv.Search(id_list=[arxiv_id])
        paper = next(arxiv.Client().results(search))
        title = re.sub(r"\s+", " ", paper.title).strip()
        if paper.authors:
            first = paper.authors[0].name.split(",")[0].strip()
            suffix = "" if len(paper.authors) == 1 else " et al"
            short_title = title[:ARXIV_SHORT_TITLE_MAX].rstrip()
            basename = f"{arxiv_id} - {first}{suffix} - {short_title}"
    except Exception:
        # Rate limit, network timeout, arxiv-id not found — any of
        # these falls back to the id-only basename, which is still
        # a stable filename.
        pass

    return basename, pdf_url


def _basename_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name or "source"


def _pdf_dest(basename: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{PAPERS_DIR}/{basename}.pdf"
    return candidate, vault.abs_path(candidate).exists()

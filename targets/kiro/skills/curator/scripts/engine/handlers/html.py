"""HTML article handler.

Fetches HTML, runs trafilatura in markdown mode, downloads inline
images to <basename>.assets/, rewrites paths to local.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from trafilatura.metadata import extract_metadata

from engine import vault
from engine.config import (
    HTTP_TIMEOUT_HTML,
    HTTP_TIMEOUT_IMAGE,
    IMG_HASH_PREFIX,
)

ARTICLES_DIR = f"{vault.SOURCES_DIR}/Articles"


def handle(url: str, wd: Path, topic: str | None = None) -> dict:
    """Fetch, extract, download images, save."""
    r = httpx.get(url, follow_redirects=True, timeout=HTTP_TIMEOUT_HTML, headers={"User-Agent": "curator/0.1"})
    r.raise_for_status()
    html = r.text
    final_url = str(r.url)

    md = trafilatura.extract(
        html,
        url=final_url,
        output_format="markdown",
        include_links=True,
        include_images=True,
        with_metadata=False,
    )
    if not md:
        raise ValueError("trafilatura returned no content")

    meta = extract_metadata(html, default_url=final_url)
    title = (meta.title if meta else None) or _title_from_url(final_url)
    author = (meta.author if meta else None) or _host_slug(final_url)
    basename = vault.slugify_basename(f"{author} - {title}")

    dest_rel = _unique_dest(basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    # Download images, rewrite paths.
    assets_dir = dest_abs.parent / f"{basename}.assets"
    md, image_log = _localize_images(md, final_url, assets_dir, wd)

    fm = {
        "type": "source",
        "origin_url": url,
        "fetched_at": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z",
        "author": author,
        "published_date": getattr(meta, "date", None) if meta else None,
        "last_updated": datetime.date.today().isoformat(),
    }
    body = f"# {title}\n\n{md}\n"
    dest_abs.write_text(vault.serialize(fm, body), encoding="utf-8")

    (wd / "meta.json").write_text(
        json.dumps(
            {"origin_url": url, "final_url": final_url, "images": image_log}, indent=2
        )
    )

    return {
        "path": dest_rel,
        "type": "article",
        "basename": basename,
    }


_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def _localize_images(md: str, base_url: str, assets_dir: Path, wd: Path) -> tuple[str, list[dict]]:
    """Download every ![]() image, rewrite src to local path, return log."""
    log = []
    urls_seen = {}

    def _sub(match):
        alt, src = match.group(1), match.group(2)
        if src.startswith("data:"):
            return match.group(0)
        abs_url = urljoin(base_url, src)
        if abs_url in urls_seen:
            local = urls_seen[abs_url]
        else:
            local = _download_image(abs_url, assets_dir)
            urls_seen[abs_url] = local
        if local is None:
            log.append({"url": abs_url, "status": "failed"})
            return match.group(0)
        log.append({"url": abs_url, "local": str(local.name), "status": "ok"})
        # Wikilink works better in Obsidian: ![[<basename>.assets/img.png]]
        rel_ref = f"{assets_dir.name}/{local.name}"
        return f"![{alt}]({rel_ref})"

    return _IMG_RE.sub(_sub, md), log


def _download_image(url: str, assets_dir: Path) -> Path | None:
    try:
        r = httpx.get(
            url,
            follow_redirects=True,
            timeout=HTTP_TIMEOUT_IMAGE,
            headers={"User-Agent": "curator/0.1"},
        )
        r.raise_for_status()
    except Exception:
        return None
    content_type = r.headers.get("content-type", "")
    ext = _ext_from_content_type(content_type) or Path(urlparse(url).path).suffix or ".bin"
    digest = hashlib.sha256(r.content).hexdigest()[:IMG_HASH_PREFIX]
    fname = f"img-{digest}{ext}"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / fname
    dest.write_bytes(r.content)
    return dest


def _ext_from_content_type(ct: str) -> str | None:
    ct = ct.split(";")[0].strip().lower()
    # Stdlib covers the common image MIME types and stays current with
    # additions; no hand-rolled map.
    return mimetypes.guess_extension(ct)


def _title_from_url(url: str) -> str:
    parsed = urlparse(url)
    last = Path(parsed.path).name or parsed.netloc
    return re.sub(r"[-_]+", " ", re.sub(r"\.html?$", "", last)).strip() or "Untitled"


def _host_slug(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "").split(".")[0]
    return host or "web"


def _unique_dest(basename: str) -> str:
    candidate = f"{ARTICLES_DIR}/{basename}.md"
    if not vault.abs_path(candidate).exists():
        return candidate
    n = 2
    while True:
        candidate = f"{ARTICLES_DIR}/{basename} ({n}).md"
        if not vault.abs_path(candidate).exists():
            return candidate
        n += 1

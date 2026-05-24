"""Google Drive handler — download via gdown, route by extension.

Drive URLs (``drive.google.com/file/d/<id>/...``,
``/uc?id=<id>``, ``/open?id=<id>``) sit behind a JS / interstitial
gate that defeats trafilatura and naive ``httpx`` downloads. ``gdown``
solves this specific case: it follows the confirm-token form for
large files, accepts cookies, and uses the original Drive filename.

The downloaded file is then routed to the same vault folder the
local handler would pick based on extension. Anything outside the
supported extension set surfaces as ``UNSUPPORTED_FORMAT`` so the
user can decide whether to broaden support or pre-convert.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import gdown

from curator import vault
from curator.source.errors import (
    HandlerError,
    HandlerErrorCode,
    reused_envelope,
    safe_handler,
)
from curator.source.handlers.local import (
    EXT_TO_FOLDER,
    _content_type_from_ext,
    _type_from_ext,
)


# ``/file/d/<ID>`` or ``/file/d/<ID>/view``. ID is the standard
# base64url-ish charset Drive uses (``_-`` allowed).
_FILE_ID_RE = re.compile(r"/file/d/([A-Za-z0-9_-]+)")


@safe_handler("gdrive")
def handle_gdrive(url: str, wd: Path) -> dict:
    """Download a Drive file via gdown and install into the vault."""
    file_id = _extract_file_id(url)
    if not file_id:
        raise HandlerError(
            HandlerErrorCode.PARSE_ERROR,
            f"unparseable Google Drive URL: {url}",
            {"url": url},
        )

    # gdown is happy to download by url+fuzzy or by id. Using the
    # id keeps us robust against URL shape variation
    # (``/view``, ``/preview``, query-only forms).
    download_dir = wd / "gdown"
    download_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Trailing slash → gdown writes into the directory using
        # the file's original Drive name.
        downloaded = gdown.download(
            id=file_id,
            output=f"{download_dir}/",
            quiet=True,
        )
    except Exception as e:
        # gdown raises broad exceptions; map to SOURCE_UNAVAILABLE
        # because the user-visible cause is "we cannot get the
        # file" regardless of underlying http vs. permission vs.
        # quota.
        raise HandlerError(
            HandlerErrorCode.SOURCE_UNAVAILABLE,
            f"gdown failed to download {file_id}: {e}",
            {"url": url, "file_id": file_id},
        ) from e

    if not downloaded:
        # gdown returns None for private files, quota'd files, and
        # files that no longer exist. The CLI prints an error
        # message but doesn't raise.
        raise HandlerError(
            HandlerErrorCode.SOURCE_UNAVAILABLE,
            "gdown returned no file (private, quota'd, or missing)",
            {"url": url, "file_id": file_id},
        )

    src = Path(downloaded)
    ext = src.suffix.lower()
    if ext not in EXT_TO_FOLDER:
        raise HandlerError(
            HandlerErrorCode.UNSUPPORTED_FORMAT,
            f"Drive file has unsupported extension: {ext}",
            {"url": url, "file_id": file_id, "filename": src.name,
             "ext": ext, "supported": sorted(EXT_TO_FOLDER.keys())},
        )

    basename = vault.slugify_basename(src.stem)
    folder = EXT_TO_FOLDER[ext]
    dest_rel, _exists = _gdrive_dest(folder, basename, ext)
    type_ = _type_from_ext(ext)
    if _exists:
        # File with the same slugified name already in the vault —
        # treat as reused and skip the move. The new download will
        # be left in wd/gdown/ and cleaned with the workdir.
        return reused_envelope(dest_rel, type_, basename)

    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), dest_abs)

    meta = {
        "origin_url":   url,
        "file_id":      file_id,
        "drive_name":   src.name,
        "size_bytes":   dest_abs.stat().st_size,
    }
    (wd / "meta.json").write_text(json.dumps(meta, indent=2))

    return {
        "path":         dest_rel,
        "type":         type_,
        "content_type": _content_type_from_ext(ext),
        "basename":     basename,
    }


def _extract_file_id(url: str) -> str | None:
    """Pull the Drive file id out of any of the common URL shapes."""
    if not isinstance(url, str):
        return None
    m = _FILE_ID_RE.search(url)
    if m:
        return m.group(1)
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    if "id" in qs and qs["id"]:
        return qs["id"][0]
    return None


def _gdrive_dest(folder: str, basename: str,
                  ext: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{folder}/{basename}{ext}"
    return candidate, vault.abs_path(candidate).exists()

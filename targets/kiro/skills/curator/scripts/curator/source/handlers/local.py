"""Local file handler — copy into the right vault folder by
extension."""
from __future__ import annotations

import shutil
from pathlib import Path

from curator import vault
from curator.source.errors import (
    HandlerError,
    HandlerErrorCode,
    reused_envelope,
    safe_handler,
)


EXT_TO_FOLDER = {
    ".pdf":      f"{vault.SOURCES_DIR}/Papers",
    ".epub":     f"{vault.SOURCES_DIR}/Books",
    ".md":       f"{vault.SOURCES_DIR}/Articles",
    ".markdown": f"{vault.SOURCES_DIR}/Articles",
}


@safe_handler("local")
def handle_local(path_str: str, wd: Path) -> dict:
    src = Path(path_str).expanduser().resolve()
    if not src.is_file():
        raise HandlerError(
            HandlerErrorCode.FILE_NOT_FOUND,
            f"local file not found: {path_str}",
            {"path": path_str},
        )

    ext = src.suffix.lower()
    if ext not in EXT_TO_FOLDER:
        raise HandlerError(
            HandlerErrorCode.UNSUPPORTED_FORMAT,
            f"unsupported local extension: {ext}",
            {"path": path_str, "ext": ext,
             "supported": sorted(EXT_TO_FOLDER.keys())},
        )

    # Already inside vault?
    vault_root = vault.VAULT_ROOT.resolve()
    try:
        rel = src.relative_to(vault_root)
        rel_s = str(rel)
    except ValueError:
        rel_s = None

    if rel_s and rel_s.startswith(vault.SOURCES_DIR + "/"):
        basename = src.stem
        type_ = _type_from_ext(ext)
        return {
            "path":         rel_s,
            "type":         type_,
            "content_type": _content_type_from_ext(ext),
            "basename":     basename,
        }

    # Copy into the right folder.
    basename = vault.slugify_basename(src.stem)
    folder = EXT_TO_FOLDER[ext]
    dest_rel, _exists = _local_dest(folder, basename, ext)
    type_ = _type_from_ext(ext)
    if _exists:
        return reused_envelope(dest_rel, type_, basename)
    dest_abs = vault.abs_path(dest_rel)
    dest_abs.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_abs)

    return {
        "path":         dest_rel,
        "type":         type_,
        "content_type": _content_type_from_ext(ext),
        "basename":     basename,
    }


def _type_from_ext(ext: str) -> str:
    return {
        ".pdf":      "pdf",
        ".epub":     "epub",
        ".md":       "article",
        ".markdown": "article",
    }.get(ext, "unknown")


def _content_type_from_ext(ext: str) -> str:
    """Map file extension to content_type.

    Kept minimal because the local handler is a pass-through — the
    classifier task downstream re-derives content from source (e.g.
    a .pdf that is a book, or a .md that is a paper draft).
    """
    return {
        ".pdf":      "paper",
        ".epub":     "book",
        ".md":       "article",
        ".markdown": "article",
    }.get(ext, "unknown")


def _local_dest(folder: str, basename: str,
                  ext: str) -> tuple[str, bool]:
    """Return (canonical vault-relative path, exists)."""
    candidate = f"{folder}/{basename}{ext}"
    return candidate, vault.abs_path(candidate).exists()

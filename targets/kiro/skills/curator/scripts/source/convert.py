"""Convert source files to transient source.md for extractor input.

The caller supplies the workdir explicitly (no workdir lifecycle
inside the source tool).
"""
from __future__ import annotations

import datetime
from pathlib import Path

from pypdf import PdfReader

from vault import vault


def convert(path: str, workdir: str | Path) -> dict:
    """Write ``<workdir>/source.md`` extracted from ``path``.

    ``path`` may be vault-relative or absolute. For .md sources,
    copies the markdown body (minus frontmatter). For .pdf, runs
    text extraction.
    """
    p = _resolve(path)
    if not p.exists():
        raise FileNotFoundError(path)

    wd = Path(workdir)
    if not wd.is_dir():
        raise FileNotFoundError(f"workdir not found: {wd}")
    out = wd / "source.md"

    ext = p.suffix.lower()
    if ext == ".md":
        text = p.read_text(encoding="utf-8")
        _, body = vault.parse(text)
        out.write_text(body, encoding="utf-8")
    elif ext == ".pdf":
        out.write_text(_pdf_to_text(p), encoding="utf-8")
    elif ext == ".epub":
        raise NotImplementedError("epub conversion not implemented in v1")
    else:
        raise ValueError(f"cannot convert: {ext}")

    return {
        "md_path": str(out),
        "workdir": str(wd),
        "basename": p.stem,
        "source_path": str(p),
        "converted_at": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z",
    }


def _resolve(path: str) -> Path:
    """Vault-relative or absolute → absolute Path."""
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    candidate = vault.VAULT_ROOT / path
    if candidate.exists():
        return candidate.resolve()
    return p.resolve()


def _pdf_to_text(p: Path) -> str:
    """Extract text from a PDF. Preserves page breaks as `\n\n---\n\n`."""
    reader = PdfReader(str(p))
    parts = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as e:
            txt = f"[extraction error on page {i+1}: {e}]"
        parts.append(f"<!-- page {i+1} -->\n{txt.strip()}")
    return "\n\n---\n\n".join(parts)

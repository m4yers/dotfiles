"""Deterministic frontmatter check exposed as ``vault validate``.

The folder ``AGENTS.md`` files describe each note format in prose;
this module pins the machine-checkable part (required keys, alias
shape, ISO dates) so format drift is caught by a script rather than
by the model noticing.
"""
from __future__ import annotations

import datetime
import re
from pathlib import PurePosixPath

from vault.config import DATE_KEYS, REQUIRED_FRONTMATTER
from vault.pages import abs_path, parse, rel_path


_ISO_DATE_RE = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")


def _top_folder(vault_path: str) -> str:
    """Top-level vault folder of a normalised vault-relative path."""
    return PurePosixPath(rel_path(abs_path(vault_path))).parts[0]


def _is_iso_date(value) -> bool:
    if isinstance(value, (datetime.date, datetime.datetime)):
        return True
    return isinstance(value, str) and bool(_ISO_DATE_RE.match(value))


def validate(vault_path: str, frontmatter: dict | None = None,
             require: tuple[str, ...] = ()) -> dict:
    """Check a note's frontmatter against its folder's rules.

    ``frontmatter`` is the proposed mapping (preview-time check);
    when ``None`` the note is read from disk, raising
    ``FileNotFoundError`` if absent. ``require`` adds keys the
    current Operations entry demands on top of the folder baseline
    in ``REQUIRED_FRONTMATTER``. Returns::

        {
          ok:       bool,
          path:     <vault-relative path>,
          folder:   <top-level folder>,
          required: [<every key checked>],
          missing:  [<required keys absent or empty>],
          errors:   [<shape problems: aliases, dates>],
        }
    """
    folder = _top_folder(vault_path)
    if frontmatter is None:
        p = abs_path(vault_path)
        if not p.exists():
            raise FileNotFoundError(vault_path)
        frontmatter, _ = parse(p.read_text(encoding="utf-8"))

    required = tuple(REQUIRED_FRONTMATTER.get(folder, ("type",)))
    required += tuple(k for k in require if k not in required)

    missing = [k for k in required
               if frontmatter.get(k) in (None, "", [], {})]

    errors: list[str] = []
    aliases = frontmatter.get("aliases")
    if aliases is not None and (
            not isinstance(aliases, list)
            or any(not isinstance(a, str) or not a.strip()
                   for a in aliases)):
        errors.append("aliases must be a list of non-empty strings")
    for key in DATE_KEYS:
        value = frontmatter.get(key)
        if value is not None and not _is_iso_date(value):
            errors.append(f"{key} must be an ISO date YYYY-MM-DD, "
                          f"got {value!r}")

    return {
        "ok":       not missing and not errors,
        "path":     rel_path(abs_path(vault_path)),
        "folder":   folder,
        "required": list(required),
        "missing":  missing,
        "errors":   errors,
    }

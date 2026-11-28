"""Load vault-root and per-folder ``AGENTS.md`` in one call.

The vault owner keeps authoritative conventions (note format,
placement rules, aliases) in these files. Pulling them inline into
one envelope saves the agent from a dozen ``fs_read`` round-trips.
"""
from __future__ import annotations

from vault.config import FOLDERS, VAULT_ROOT


# Top-level folder names that have an ``AGENTS.md`` the agent may
# request. Pre-computed from the kind map so unknown folders raise
# cleanly.
_ALLOWED_FOLDERS = frozenset(FOLDERS.values())


def _read_if_exists(abs_path) -> tuple[str | None, str | None]:
    """Return ``(text, None)``, or ``(None, "missing")`` when the file
    does not exist, or ``(None, "unreadable: <err>")`` when it cannot
    be read."""
    if not abs_path.exists():
        return None, "missing"
    try:
        return abs_path.read_text(encoding="utf-8"), None
    except (OSError, UnicodeDecodeError) as e:
        return None, f"unreadable: {e}"


def load_agents(folders: list[str]) -> dict:
    """Read the vault-root ``AGENTS.md`` + each folder's ``AGENTS.md``.

    Rejects unknown folder names so a typo surfaces loudly, and
    raises ``ValueError`` when the root ``AGENTS.md`` or any
    requested folder's ``AGENTS.md`` is missing or unreadable, so
    the caller can never proceed with null folder rules. Returns::

        {
          root_agents: "<text>",
          folder_agents: {"10 SOURCES": "<text>", ...},
        }
    """
    unknown = [f for f in folders if f not in _ALLOWED_FOLDERS]
    if unknown:
        raise ValueError(
            f"unknown vault folder(s): {', '.join(unknown)}")

    root_path = VAULT_ROOT / "AGENTS.md"
    root_text, root_err = _read_if_exists(root_path)
    if root_text is None:
        raise ValueError(f"root AGENTS.md {root_err}: {root_path}")

    folder_texts: dict = {}
    problems: list[str] = []
    for folder in folders:
        path = VAULT_ROOT / folder / "AGENTS.md"
        text, err = _read_if_exists(path)
        if text is None:
            problems.append(f"{folder}: AGENTS.md {err}")
            continue
        folder_texts[folder] = text
    if problems:
        raise ValueError(
            "folder AGENTS.md unavailable: " + "; ".join(problems))

    return {
        "root_agents":   root_text,
        "folder_agents": folder_texts,
    }

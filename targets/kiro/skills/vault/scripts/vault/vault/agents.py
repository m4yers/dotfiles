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


def _read_if_exists(abs_path) -> str | None:
    """Return the file's text, or ``None`` if it does not exist."""
    if not abs_path.exists():
        return None
    try:
        return abs_path.read_text(encoding="utf-8")
    except OSError:
        return None


def load_agents(folders: list[str]) -> dict:
    """Read the vault-root ``AGENTS.md`` + each folder's ``AGENTS.md``.

    Rejects unknown folder names so a typo surfaces loudly.
    Returns::

        {
          root_agents: "<text or null>",
          folder_agents: {"10 SOURCES": "<text or null>", ...},
          missing: [<folders with no AGENTS.md on disk>],
        }
    """
    unknown = [f for f in folders if f not in _ALLOWED_FOLDERS]
    if unknown:
        raise ValueError(
            f"unknown vault folder(s): {', '.join(unknown)}")

    root_text = _read_if_exists(VAULT_ROOT / "AGENTS.md")

    folder_texts: dict = {}
    missing: list[str] = []
    for folder in folders:
        text = _read_if_exists(VAULT_ROOT / folder / "AGENTS.md")
        folder_texts[folder] = text
        if text is None:
            missing.append(folder)

    return {
        "root_agents":   root_text,
        "folder_agents": folder_texts,
        "missing":       missing,
    }

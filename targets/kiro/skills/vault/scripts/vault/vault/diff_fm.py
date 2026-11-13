"""Diff a page's current frontmatter against a baseline.

Obsidian rewrites frontmatter on save — leading-zero IDs lose their
zeroes, strings may acquire or lose quotes, ordering can change.
A diff against the baseline catches these silently-destructive
rewrites so the agent can warn or abort.
"""
from __future__ import annotations

from pathlib import Path

from vault.pages import abs_path, parse


def diff_fm(vault_path: str,
             baseline: dict | None = None) -> dict:
    """Compare current frontmatter against ``baseline``.

    ``baseline=None`` reads the current frontmatter and returns it
    as the baseline (``changed=False``) so callers can store it for
    the next comparison.

    Returns::

        {
          changed:  bool,
          baseline: {<the baseline used>},
          current:  {<current frontmatter>},
          added:    [<key, ...>],
          removed:  [<key, ...>],
          modified: [{key, before, after}],
        }
    """
    p = abs_path(vault_path)
    if not p.exists():
        raise FileNotFoundError(vault_path)
    current, _ = parse(p.read_text(encoding="utf-8"))

    if baseline is None:
        return {
            "changed":  False,
            "baseline": current,
            "current":  current,
            "added":    [],
            "removed":  [],
            "modified": [],
        }

    added    = sorted(set(current) - set(baseline))
    removed  = sorted(set(baseline) - set(current))
    modified = [
        {"key": k, "before": baseline[k], "after": current[k]}
        for k in sorted(set(baseline) & set(current))
        if baseline[k] != current[k]
    ]
    changed = bool(added or removed or modified)

    return {
        "changed":  changed,
        "baseline": baseline,
        "current":  current,
        "added":    added,
        "removed":  removed,
        "modified": modified,
    }

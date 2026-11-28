"""Diff a page's current frontmatter against a baseline.

Obsidian rewrites frontmatter on save — leading-zero IDs lose their
zeroes, strings may acquire or lose quotes, ordering can change.
A diff against the baseline catches these silently-destructive
rewrites so the agent can warn or abort.
"""
from __future__ import annotations

import datetime

from vault.pages import abs_path, parse


def _normalize(value):
    """Render dates as ISO strings, recursively.

    ``yaml.safe_load`` turns ``2024-01-01`` into a ``date`` while a
    JSON or re-emitted baseline may carry the same value as a
    string. Normalising both sides keeps a round-trip of the YAML
    this command emits from reporting spurious modifications.
    """
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def diff_fm(vault_path: str, baseline: dict) -> dict:
    """Compare current frontmatter against ``baseline``.

    ``baseline`` is required: the caller captures it before the
    edit (``vault read``) so the diff can surface Obsidian
    rewrites. Dates on both sides are normalised to ISO strings.

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
    current = _normalize(current)
    baseline = _normalize(baseline)

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

"""Quintet classification — vocabularies + extractor rule matching.

Vocabularies, semantic descriptions, and rules live in
``<skill_root>/quintet.yaml``. This module is a thin loader + matcher;
to add new extractor combinations or new slot values, edit the YAML.

The quintet ``(media, form, register, discipline, audience)`` captures
a source's nature across five orthogonal dimensions. Every slot takes
one value from a constrained vocabulary; the classifier prompt is
populated from the same YAML so descriptions stay in sync.

Rules are additive: every rule whose pattern matches the quintet
contributes its extractor list to the union. Broad base rules set the
floor; specific rules stack capability on top. Duplicates are deduped
(first-seen wins on ordering).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Tuple

import yaml


# Skill root: <skill>/scripts/curator/quintet.py → <skill>/
_SKILL_ROOT  = Path(__file__).resolve().parent.parent.parent
_QUINTET_FILE = _SKILL_ROOT / "quintet.yaml"


@lru_cache(maxsize=1)
def _load() -> dict:
    """Parse quintet.yaml once per process."""
    if not _QUINTET_FILE.exists():
        raise FileNotFoundError(
            f"quintet.yaml not found at {_QUINTET_FILE}")
    return yaml.safe_load(_QUINTET_FILE.read_text(encoding="utf-8"))


def slots() -> dict:
    """Return the parsed ``slots`` block as-is.

    Each entry is `{description: str, values: {<value>: <description>}}`.
    Used by prompt rendering to inject vocabularies + descriptions.
    """
    return _load()["slots"]


def _values(slot: str) -> Tuple[str, ...]:
    return tuple(_load()["slots"][slot]["values"].keys())


# Backwards-compat constants — generated from the YAML at import time.
MEDIA      = _values("media")
FORM       = _values("form")
REGISTER   = _values("register")
DISCIPLINE = _values("discipline")
AUDIENCE   = _values("audience")


def validate_quintet(q: dict) -> None:
    """Raise ValueError if any slot is absent or not in its vocabulary."""
    s = _load()["slots"]
    for slot, info in s.items():
        if slot not in q:
            raise ValueError(f"quintet missing slot: {slot!r}")
        vocab = info["values"]
        if q[slot] not in vocab:
            raise ValueError(
                f"quintet slot {slot!r}={q[slot]!r} not in vocabulary "
                f"{list(vocab.keys())!r}"
            )


def extractors_for(quintet: dict) -> list[str]:
    """Return the union of extractor kinds for every matching rule.

    Preserves first-seen ordering; silently dedupes duplicates. The
    base ``(*, *, *, *, *)`` row guarantees a non-empty result.
    """
    rules = _load()["rules"]
    key = (
        quintet["media"], quintet["form"], quintet["register"],
        quintet["discipline"], quintet["audience"],
    )
    result: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        rule_key = tuple(rule["match"])
        if all(a == "*" or a == b for a, b in zip(rule_key, key)):
            for e in rule["extractors"]:
                if e not in seen:
                    result.append(e)
                    seen.add(e)
    return result


def all_extractors() -> list[str]:
    """Return every extractor kind referenced by any rule (deduped)."""
    rules = _load()["rules"]
    seen: set[str] = set()
    out: list[str] = []
    for rule in rules:
        for e in rule["extractors"]:
            if e not in seen:
                out.append(e)
                seen.add(e)
    return out

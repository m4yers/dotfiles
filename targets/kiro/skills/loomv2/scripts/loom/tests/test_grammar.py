"""Invariants for the reference-placeholder GRAMMAR table.

Every ``GRAMMAR`` row MUST have a compilable regex the resolver dispatches
against, because the same table backs both parser behaviour and
``references/grammar.md``.
"""
from __future__ import annotations

import re

from loom.engine.resolve import GRAMMAR, resolve


def test_every_row_has_compilable_regex_and_description():
    assert GRAMMAR, "GRAMMAR table is empty"
    for row in GRAMMAR:
        assert row.token, "row missing token"
        assert row.description, f"{row.token} missing description"
        assert re.compile(row.regex)


def test_every_row_is_exercised_by_resolver():
    """Each row's regex must match at least one sample derived from the token."""
    samples = {
        "$${...}": "$${foo}",
        "${workdir}": "${workdir}",
        "${task_workdir}": "${task_workdir}",
        "${task:<addr>@<k>}": "${task:foo@3}",
        "${task:<addr>@prev}": "${task:foo@prev}",
        "${task:<addr>:<jmespath>}": "${task:foo:a.b}",
        "${task:<addr>}": "${task:foo}",
        "${task_path:<addr>}": "${task_path:foo}",
        "${input:<jmespath>}": "${input:a.b}",
    }
    assert set(samples) == {row.token for row in GRAMMAR}, (
        "GRAMMAR tokens drifted from test samples"
    )
    for row in GRAMMAR:
        assert re.search(row.regex, samples[row.token]), (
            f"{row.token} regex did not match its sample"
        )


def test_resolve_leaves_unknown_placeholders():
    out = resolve("${task:missing}", {})
    assert out == "${task:missing}"

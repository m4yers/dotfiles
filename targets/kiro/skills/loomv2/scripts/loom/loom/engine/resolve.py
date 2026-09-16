"""Placeholder + JMESPath resolution driven by a single GRAMMAR table.

The parser dispatches against the same list documented in
``references/grammar.md``, so parser and docs cannot drift. Placeholders
feed graph.yaml ``input:`` mappings and ``when`` / ``while_``
predicates — the two surfaces where the engine reaches across task
boundaries. Composition rewrites parent-side ``${task:<subgraph-id>...}``
at inline time; ``${workdir}`` inside child tasks resolves against the
ROOT run.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class GrammarRow:
    """One placeholder form. ``regex`` is the recognisor; ``description``
    is the doc surface (see ``references/grammar.md``)."""

    token: str
    regex: str
    description: str


# Order matters: escape rule first, then most-specific to least-specific.
GRAMMAR: list[GrammarRow] = [
    GrammarRow(
        token="$${...}",
        regex=r"\$\$\{[^}]*\}",
        description="Literal ${...}. Escape hatch — resolver leaves this untouched.",
    ),
    GrammarRow(
        token="${workdir}",
        regex=r"\$\{workdir\}",
        description="Absolute path to the ROOT workdir. Child tasks share this.",
    ),
    GrammarRow(
        token="${task_workdir}",
        regex=r"\$\{task_workdir\}",
        description="Absolute path to the current task's folder.",
    ),
    GrammarRow(
        token="${task:<addr>@<k>}",
        regex=r"\$\{task:([^:}@]+)@(\d+)\}",
        description="Loop body: absolute round k output.",
    ),
    GrammarRow(
        token="${task:<addr>@prev}",
        regex=r"\$\{task:([^:}@]+)@prev\}",
        description="Loop body: the round before the latest completed round.",
    ),
    GrammarRow(
        token="${task:<addr>:<jmespath>}",
        regex=r"\$\{task:([^:}]+):([^}]+)\}",
        description="Upstream task output projected via JMESPath.",
    ),
    GrammarRow(
        token="${task:<addr>}",
        regex=r"\$\{task:([^:}@]+)\}",
        description="Latest completed round of upstream task's output.yaml.",
    ),
    GrammarRow(
        token="${task_path:<addr>}",
        regex=r"\$\{task_path:([^}]+)\}",
        description="Absolute path to upstream task folder.",
    ),
    GrammarRow(
        token="${input:<jmespath>}",
        regex=r"\$\{input:([^}]+)\}",
        description="Current task's input.yaml projected via JMESPath.",
    ),
]


def resolve(text: str, context: dict[str, str]) -> str:
    """Substitute placeholders in ``text`` using ``context``.

    ``context`` supplies precomputed values keyed by the placeholder
    token (e.g. ``'${workdir}'`` → path). The resolver only performs
    literal substitution; upstream code is responsible for building
    ``context`` correctly per-task.

    Unknown placeholders remain as-is so validation layers can flag them.
    """
    out = text
    for row in GRAMMAR:
        if row.token == "$${...}":
            continue  # handled by _restore_escapes below
        out = re.sub(row.regex, lambda m, r=row: context.get(m.group(0), m.group(0)), out)
    return _restore_escapes(out)


def _restore_escapes(text: str) -> str:
    """Turn $${...} into ${...}."""
    return re.sub(r"\$\$\{([^}]*)\}", r"${\1}", text)


def rename_refs(text: str, mapper: Callable[[str], str]) -> str:
    """Rewrite ${task:<addr>...} placeholders through ``mapper``.

    Used by engine.inline to prefix child-local refs with the child
    namespace at inline time.
    """
    def _sub(match: re.Match) -> str:
        raw = match.group(0)
        # Skip escaped forms.
        if raw.startswith("$$"):
            return raw
        # Extract the address (the part after ':' until ':' or '@' or '}').
        m = re.match(r"\$\{task:([^:}@]+)", raw)
        if not m:
            return raw
        addr = m.group(1)
        new_addr = mapper(addr)
        return raw.replace(addr, new_addr, 1)

    return re.sub(r"\$\{task:[^}]+\}", _sub, text)

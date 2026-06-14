"""dojo.autochecks — automated convention checks.

Re-exports the public API from ``checks`` (engine + output
adapters). Per-rule check implementations live in sibling
modules (``authoring``, ``script_conventions``, etc.).
"""
from dojo.autochecks.checks import (  # noqa: F401
    lint_skill, lint_to_findings, lint_to_text,
)

__all__ = ["lint_skill", "lint_to_findings", "lint_to_text"]

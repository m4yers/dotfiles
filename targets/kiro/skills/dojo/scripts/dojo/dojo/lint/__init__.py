"""dojo.lint — automated convention checks.

Re-exports `lint_skill` from `checks` (the actual check
implementations live there, ported from the original
skill-lint.py). The `runner` module converts findings into the
shape required by `findings.yaml`.
"""
from dojo.lint.checks import lint_skill  # noqa: F401

__all__ = ["lint_skill"]

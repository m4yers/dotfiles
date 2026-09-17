"""Child task — stubbed lint."""
from io_types import LintTextInput, LintTextOutput


def lint_text(inp: LintTextInput) -> LintTextOutput:
    return LintTextOutput(
        issues_found=0,
        notes=f"Linted {len(inp.greeting)} chars.",
    )

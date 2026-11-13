"""CLI entrypoint. Delegates to the typer app in vault.cli."""
from __future__ import annotations

from vault.cli import app


if __name__ == "__main__":
    app()

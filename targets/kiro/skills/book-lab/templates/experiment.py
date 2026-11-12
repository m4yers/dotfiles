# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich",
#     "numpy",
# ]
# ///
"""One-line description of what this experiment computes.

Replace this docstring with the concept or exercise being
explored, and the formula or model it implements.
"""

from __future__ import annotations

import argparse

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--n",
        type=int,
        default=1000,
        help="Sample size / iterations. Default: 1000",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="RNG seed for reproducibility. Default: 0",
    )
    args = parser.parse_args()

    console = Console()
    console.print(Panel(f"n={args.n}  seed={args.seed}", expand=False))

    table = Table(show_header=True, header_style="bold")
    table.add_column("quantity", justify="left")
    table.add_column("value", justify="right")
    table.add_row("TODO", "—")
    console.print(table)


if __name__ == "__main__":
    main()

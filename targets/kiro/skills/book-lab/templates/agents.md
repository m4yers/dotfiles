# Worked Examples

Chapter-by-chapter code experiments accompanying a book. Each
experiment is a small, self-contained script that explores one
concept, exercise, or side-question from the text.

## Folder structure

One folder per part, one subfolder per chapter. Chapter folders
are created only when code for that chapter is requested — no
empty scaffolding.

```
.
├── AGENTS.md                          # this file
├── PartI/
│   ├── Chapter1/                      # created on demand
│   ├── Chapter2/
│   │   ├── experiment_a.py            # one script per experiment
│   │   ├── experiment_b.py
│   │   └── ...
│   └── ...
├── PartII/
│   └── ...
└── ...
```

## Script conventions

- **Language**: plain Python 3.
- **Package manager**: [`uv`](https://docs.astral.sh/uv/).
- **Dependency declaration**: PEP 723 inline script metadata at
  the top of each script. No `pyproject.toml`, no per-folder
  venv.
- **CLI**: `argparse`. Every tweakable parameter (sample size,
  seed, horizon, bet size, ...) is a flag with a sensible
  default.
- **Output**: terminal only, rendered via
  [`rich`](https://rich.readthedocs.io/) — tables, panels,
  progress bars. No files written unless an experiment
  specifically needs it.
- **One experiment per file**. A chapter with multiple distinct
  experiments gets multiple scripts, not one script with
  subcommands.

## Script template

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "rich",
#     "numpy",
# ]
# ///
"""Short description of what this experiment computes."""

import argparse
# ...

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=1000)
    # ... other tweakables
    args = parser.parse_args()

    # crunch numbers
    # render with rich

if __name__ == "__main__":
    main()
```

## Running

From the chapter folder:

```bash
uv run experiment_a.py --n 10000 --seed 1
```

`uv` resolves the inline dependencies, caches them, and runs the
script. No manual venv activation.

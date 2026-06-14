# Script Conventions

Rules for skill scripts: APIs, oracles, packaging, and contracts.

## Contents

- [1. Script APIs](#1-script-apis)
- [2. Executable Oracles](#2-executable-oracles)
- [3. Script Invocation Paths](#3-script-invocation-paths)
- [4. Language Choice](#4-language-choice)
- [5. Python Scripts](#5-python-scripts)
- [6. Rendering Jinja Templates](#6-rendering-jinja-templates)
- [7. Magic Constants](#7-magic-constants)
- [8. Stdlib First](#8-stdlib-first)
- [9. Producer/Consumer Contracts](#9-producerconsumer-contracts)

## 1. Script APIs

1. Repeatable, verifiable actions MUST be encoded as scripts that expose an
   opaque API.
2. Callers MUST use named commands; scripts MUST hide the underlying tool (tmux,
   vim, git internals).
3. Constraints MUST be enforced in code, not in prose for the caller, because a
   rule in code cannot be violated.
4. Internal state (pane IDs, editor commands, temp paths) MUST stay inside the
   script; the API MUST expose named operations and structured output.
5. Scripts MUST handle errors explicitly — create missing files, supply
   defaults, emit actionable messages — and MUST NOT fail silently, because that
   leaves the model to guess.

## 2. Executable Oracles

1. Verifiable outcomes MUST be checked by a deterministic oracle (script,
   linter, test, schema validator), not by the LLM eyeballing the result.
2. Oracles are NOT REQUIRED for verifiable actions like scripts, because a
   non-zero exit already enforces correctness.
3. Oracles MUST target outcomes the exit code does not enforce: semantic
   content, user-facing behaviour, cross-script invariants.
4. Every step that produces output MUST be followed by a verification sub-step
   that runs the oracle.
5. Each oracle sub-step MUST document the command, what "pass" looks like (exit
   0, specific output), and what "fail" triggers (which sub-step to retry, when
   to escalate).

## 3. Script Invocation Paths

1. Skills MUST invoke scripts through uppercase env vars whose names match the
   target script's basename (hyphens → underscores). (check:
   `autochecks/script_conventions.py:49`)

2. Each env var MUST be declared once at the top of Step 1 and reused for every
   invocation. (check: `autochecks/script_conventions.py:12`)

```bash
DOJO=~/.kiro/skills/home/dojo/scripts/dojo.sh
TILING=~/.kiro/skills/home/tiling/scripts/run-ttm.sh

$DOJO ingest --op create --name my-skill
$TILING activity set "..."
```

## 4. Language Choice

1. Bash MAY be used only for short shims (env setup, exec, no logic).

2. Any script with argument parsing, loops over command output, or more than ~10
   non-blank/non-comment code lines MUST be Python, because beyond that size
   bash quoting and error propagation become fragile. (check:
   `autochecks/script_conventions.py:83`)

3. Acceptable bash patterns are: a shim that execs a uv/python command, an
   env-detection script that prints shell assignments for `eval`, and a
   single-line `exec` wrapper.

## 5. Python Scripts

1. Stdlib-only scripts MUST be a single file without `pyproject.toml`, invoked
   directly via `python3`.

2. Each dependency-using package under `scripts/` MUST have its own
   `pyproject.toml` and `uv.lock` at the package root. (check:
   `autochecks/script_conventions.py:114`)

3. Each dependency-using package MUST be invoked through a `.sh` shim in
   `scripts/` that runs `uv run --project ... python -m`.

4. Callers MUST invoke the `.sh` shim, not the package internals.

5. `.venv/` MUST be gitignored at any depth.

6. `uv.lock` MUST be committed, because installs MUST be reproducible.

```
scripts/
├── classifier.py              (stdlib-only single file)
├── reporter.sh                (shim for reporter package)
└── reporter/                  (dep-using package)
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── pyproject.toml
    └── uv.lock
```

```toml
[project]
name = "reporter"
version = "0.1.0"
requires-python = ">=3.7"
dependencies = [ "package>=version",]
```

```bash
#!/usr/bin/env bash
# reporter.sh — shim for `python -m reporter` via uv.
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/reporter" \
    python -m reporter "$@"
```

## 6. Rendering Jinja Templates

1. Skills rendering Jinja templates MUST use the `template` skill rather than
   vendoring `jinja2`, because `template` owns that dependency and provides one
   shared venv, a strict-undefined renderer, and a consistent error surface.
2. `--var KEY=VALUE` MAY be used only for trivial scalars.
3. Callers MUST capture stdout to a file or pipe; a non-zero exit MUST be
   treated as a render failure.

```bash
TEMPLATE=~/.kiro/skills/home/template/scripts/render.sh

$TEMPLATE \
    --template /path/to/my-template.md.j2 \
    --include-dir /path/to/template-dir \
    --json-vars /tmp/my-skill-vars.json \
    > /target/output.md
```

## 7. Magic Constants

1. Hardcoded numbers, timeouts, retry counts, buffer sizes, and thresholds MUST
   carry a comment explaining the value, because uncommented magic numbers are
   unreviewable.

```python
# 30s — matches the upstream Lambda timeout; raising
# this requires raising both.
TIMEOUT_SECONDS = 30
```

## 8. Stdlib First

1. Scripts MUST NOT reimplement functionality available in the Python stdlib
   (`pathlib`, `shutil`, `textwrap`, `json`, `argparse`, `re`, `subprocess`,
   `tempfile`) or standard Linux tools (`find`, `grep`, `sort`, `jq`, `sed`,
   `awk`), because custom forks drift from edge cases and burden reviewers with
   comparing the two.
2. Authors MUST check stdlib and existing project utilities before writing a
   path walker, CSV parser, templating substituter, or retry loop.

## 9. Producer/Consumer Contracts

1. When one script's output feeds another, the producer's output schema MUST
   match the consumer's expected input.
2. The producer MUST document its schema in `--help` or a docstring.
3. The consumer MUST read that exact shape, with no rename, projection, or
   remap.
4. A `schemas/` file SHOULD be referenced by both sides when the contract is
   more than a flat dict.
5. If a SKILL instructs the agent to "transform between steps" or "extract field
   X from Y's output", the producer's shape MUST be fixed instead, because that
   runtime glue is exactly the manual work scripts exist to eliminate.

# Script Conventions

Rules for skill scripts: APIs, executable oracles, and
Python packaging. Split from `conventions.md` to keep
each reference file under 300 lines.

## Contents

- [Script APIs](#script-apis)
- [Executable Oracles](#executable-oracles)
- [Python Scripts](#python-scripts)
- [Rendering Jinja Templates](#rendering-jinja-templates)

## Script APIs

Skills that perform repeatable, verifiable actions MUST
encode them as scripts and expose them as an opaque API
(like `tiling` and `editor` do). Callers use named
commands — they should not know about the underlying
tool (tmux, vim, git internals, etc.).

- If an action can be a script, it should be — not prose
  instructions the agent re-interprets each time.
- Enforce constraints in the script (validation, defaults)
  rather than documenting rules for callers. A rule
  enforced in code cannot be violated.
- Internal state (pane IDs, editor commands, temp file
  paths) stays inside the script. Expose named operations
  and structured output instead.
- **Solve, don't punt** — scripts should handle error
  conditions explicitly (create missing files, provide
  defaults, give actionable error messages) rather than
  failing and leaving the model to figure it out.
- **No magic constants** — every hardcoded value in a
  script should have a comment explaining why that value
  was chosen. If you cannot justify it, the model cannot
  either.

## Multi-field CLI arguments

When a single CLI argument carries multiple fields (e.g.
`--foo id:cat:hint`), pick a delimiter that cannot appear
in any field's value. `:` is a poor default because
`file:line` references commonly appear inside hints,
evidence, paths, and error messages. Prefer `|` or
another character absent from the expected values.

- Parse with `str.split(delim)` that fails on wrong field
  count — do not rely on `partition` / `rpartition`
  heuristics, which silently split the last occurrence of
  a delimiter that the field itself contains.
- Document the delimiter choice in the script's help and
  in any template that generates the argument.

## Executable Oracles

When a skill step produces a verifiable outcome, that
outcome MUST be checked by an automated oracle — not by
the LLM eyeballing the result. The LLM cannot be trusted
to judge its own output.

An oracle is any deterministic check: a script, a linter,
a test suite, a diff, a schema validator, a file-existence
check. If the verification does not require LLM reasoning,
it MUST NOT be left to the LLM because LLMs cannot
reliably judge their own output.

### The two rules

1. **Repeatable action → script.** If an action is
   deterministic and will be performed the same way every
   time, it MUST be a script. Prose instructions that the
   LLM re-interprets each invocation are a degree of
   freedom that produces inconsistent results.

2. **Verifiable outcome → oracle.** If a step's success
   can be checked without LLM reasoning, the skill MUST
   specify the oracle. The LLM MUST suggest which oracle
   to use when authoring the skill.

   **Exclusion:** Do not add an oracle that verifies a
   file or directory a script just created. A script's
   non-zero exit already enforces that invariant —
   `test -f <path>` after `mkdir -p` / `touch` is
   redundant. Oracles apply to outcomes the script's exit
   code does NOT enforce: semantic content, user-facing
   behavior, cross-script invariants.

### Oracle placement in skills

After any step that produces output, add a verification
sub-step that runs the oracle. Document:
- What command to run
- What "pass" looks like (exit code 0, specific output)
- What "fail" means (which sub-step to retry or when to
  escalate)

### Examples

| Outcome to verify          | Oracle                        |
|----------------------------|-------------------------------|
| Code compiles              | `<build-tool>`                |
| Tests pass                 | `<test-tool>`                 |
| Markdown well-formed       | `skill-lint.py`               |
| No trigger overlaps        | `dojo.sh check overlaps` |
| Script has --help          | `<script> --help >/dev/null`  |
| JSON valid                 | `python3 -m json.tool`        |

### What the LLM must do at authoring time

When creating a skill, for each step that produces a
verifiable outcome, the LLM MUST:
1. Identify the outcome
2. Propose an oracle (existing script, new script, or
   shell one-liner)
3. Add the oracle as a verification sub-step
4. Document pass/fail criteria

## Script Invocation Paths

SKILL.md bodies and reference files MUST invoke scripts via the
`$SKILLS` shell variable (`$SKILLS = ~/.kiro/skills`) rather than
hardcoding `~/.kiro/skills/...` in every code block. Skills that
call multiple scripts declare `SKILLS` once at the top of Step 1
and reuse it throughout:

```bash
SKILLS=~/.kiro/skills
$SKILLS/home/tiling/scripts/run-ttm.sh activity set "..."
$SKILLS/home/skill-analytics/scripts/add-invocation.sh <skill> <trigger>
```

Rules:

- Inside fenced code blocks, script paths MUST use `$SKILLS/...`,
  not `~/.kiro/skills/...`.
- The first step of the workflow sets `SKILLS=~/.kiro/skills`.
- Dependency lists and prose references to sibling `SKILL.md`
  files keep the literal `~/.kiro/skills/...` form because they
  are documentation paths a human navigates to, not shell
  commands.
- Python scripts that need the skills root should honor a
  `SKILLS` env var with a fallback:
  `os.environ.get("SKILLS", os.path.expanduser("~/.kiro/skills"))`.

The variable decouples skills from the hardcoded install path
and keeps invocations short; the name `SKILLS` is reserved —
skills MUST NOT redefine it.

## Env Var Propagation

Scripts that need to set environment variables in the caller's
shell MUST print shell assignments to stdout and be consumed via
`eval "$(...)"`. A subprocess cannot modify its parent's
environment directly — `export VAR=...` inside the script only
affects the script itself and dies when it exits.

Example producer (`detect-workspace.sh`):

```bash
if WORKSPACE_ROOT="$(workspace-tool path)"; then
  echo "WORKSPACE_ROOT='$WORKSPACE_ROOT'"
else
  echo "echo 'ERROR: no workspace' >&2; exit 1"
  exit 1
fi
```

Example caller (in SKILL.md):

```bash
eval "$($SKILLS/<ns>/<skill>/scripts/detect-workspace.sh)"
```

Rules:

- Scripts that emit env assignments MUST document every VAR they
  print in the script's `--help` output or top docstring. The
  docstring lists each VAR, its meaning, and when it is unset.
- Agent shell calls are independent subprocesses — vars set in
  one call do not persist to the next. Every SKILL.md step that
  needs a propagated var MUST re-eval the producer at the top of
  its code block, or include the var-producing command in the
  same code block as its consumer.
- JSON or other structured output MUST NOT be used for env
  propagation because it cannot be fed to `eval`. If a script
  has structured output for inspection AND env vars to
  propagate, split into two modes or two scripts.

## Language Choice

Prefer Python. Use bash only for short shims (environment
setup, exec, no complex logic). Any script with argument
parsing, loops over command output, or more than ~10
non-blank/non-comment code lines should be Python.

skill-lint enforces the threshold: bash scripts with >10
code lines emit a warning recommending conversion. The
threshold exists because bash's argument handling,
quoting, and error propagation become fragile above that
size, and Python's stdlib covers the same ground with
fewer footguns.

Common bash-valid patterns:
- Shim that runs a uv/python command and execs the result
- Env detection (`detect-workspace.sh`) that prints shell
  assignments for `eval`
- Single-line wrapper with `exec`

## Python Scripts

Two rules based on whether the script has external deps:

### No dependencies (stdlib only)

Run directly:
```bash
python3 $SKILLS/{category}/{name}/scripts/script.py
```

No `pyproject.toml` needed.

### With dependencies

Each dependency-using Python package under `scripts/` has its
OWN `pyproject.toml` and `uv.lock` at the package root:

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

`pyproject.toml` contents. The `name` field MUST follow the
`<skill-name>-<package>` pattern so each package is uniquely attributable
to its skill:

```toml
[project]
name = "skill-name-reporter"
version = "0.1.0"
requires-python = ">=3.7"
dependencies = ["package>=version"]
```

Create a shim shell script in `scripts/` that runs the package
via uv, pointing at the package dir:

```bash
#!/usr/bin/env bash
# reporter.sh — shim for `python -m reporter` via uv.
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
exec env PYTHONPATH="${SCRIPTS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
    uv run --project "$SCRIPTS_DIR/reporter" \
    python -m reporter "$@"
```

Callers invoke the `.sh` shim, not the package internals.

Rules:

- One `pyproject.toml` / `uv.lock` per dep-using package. Do NOT
  put a top-level `scripts/pyproject.toml` that covers multiple
  packages — each package scopes its own deps.
- Stdlib-only packages (and single-file scripts) do not need a
  `pyproject.toml`.
- uv creates a `.venv/` inside each package's directory. All
  `.venv/` entries are gitignored (one `.venv/` line matches at
  any depth).
- Lock files (`uv.lock`) ARE committed so installs are
  reproducible.

## Rendering Jinja Templates

Skills that render Jinja templates (to produce config files,
agent prompts, generated markdown, etc.) MUST use the `template`
skill rather than vendoring `jinja2` in their own package or
re-implementing rendering. The `template` skill exists for this
exact purpose — one shared venv, one strict-undefined renderer,
one consistent error surface.

Invocation pattern (from `~/.kiro/skills/home/curator` and
`dojo` itself):

```bash
SKILLS=~/.kiro/skills

# Log activation once.
$SKILLS/home/skill-analytics/scripts/add-invocation.sh \
    template skill:my-skill

# Render with vars from a JSON file (preferred for multi-line
# strings) or repeated --var flags.
$SKILLS/home/template/scripts/render.sh \
    --template /path/to/my-template.md.j2 \
    --include-dir /path/to/template-dir \
    --json-vars /tmp/my-skill-vars.json \
    > /target/output.md
```

Rules:

- Skills MUST NOT add `jinja2` to their own `pyproject.toml`
  for rendering — the `template` skill owns that dependency.
- The `--include-dir` flag is required when (a) the template
  uses `{% raw %}{% include %}{% endraw %}`, OR (b) the
  template path is not under the caller's CWD. Pass
  `--include-dir` once per directory (repeatable). Both the
  template's own folder AND any partials' folders must be
  included.
- Pass structured / multi-line variables via `--json-vars` and
  a temp JSON file. Use `--var KEY=VALUE` only for trivial
  scalar strings.
- Capture stdout to a file or pipe to a downstream consumer.
  `render.sh` writes errors to stderr; non-zero exit codes
  always indicate a render failure.
- Exception: skills that use loom may produce prompt templates
  for tasks (rendered by loom internally). Those templates do
  NOT need `template/render.sh` — loom calls them during
  `next()`. The rule applies only to standalone Jinja
  rendering outside the loom DAG.


## Magic Constants

Hardcoded numeric values, timeouts, retry counts, buffer sizes,
or thresholds in scripts MUST carry a justifying comment
explaining why the value was chosen. Uncommented magic numbers
make scripts hard to tune and impossible to review for
correctness — a future reader cannot tell whether `30` is a
hard requirement or a placeholder.

```python
# 30s — matches the upstream Lambda timeout; raising
# this requires raising both.
TIMEOUT_SECONDS = 30
```

## Stdlib First

Scripts MUST NOT reimplement functionality available in the
Python stdlib (`pathlib`, `shutil`, `textwrap`, `json`,
`argparse`, `re`, `subprocess`, `tempfile`) or standard Linux
tools (`find`, `grep`, `sort`, `jq`, `sed`, `awk`). A custom
implementation forks behaviour, drifts from the stdlib's
edge cases, and burdens reviewers with deciding whether the
custom version matches the standard one.

If you find yourself writing a path walker, a CSV parser, a
templating substituter, or a retry loop, check the stdlib and
the project's existing utilities first.

## Producer/Consumer Contracts

When one script's output file is consumed by another script
(data pipeline), the producer's output schema MUST match the
consumer's expected input. Mismatches force the agent to write
ad-hoc glue scripts at runtime — exactly the manual work scripts
exist to eliminate.

For each pipeline step:

- The producer's schema (or argparse-derived structure) is
  documented in its `--help` or docstring.
- The consumer reads that exact shape; no rename, projection,
  or remap.
- A schema file under `schemas/` SHOULD be referenced by both
  sides when the contract is more than a flat dict.

If the SKILL.md instructs the agent to "transform between
steps" or "extract field X from Y's output", the producer is
emitting the wrong shape — fix the producer, not the workflow.
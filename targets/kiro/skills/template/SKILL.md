---
name: template
type: interface
description: Render jinja2 templates with variables from the command line. Use when a skill needs to produce text from a template — agent prompts, config files, generated markdown. Other skills invoke scripts/render.sh and pass the output to the consumer (sub-agent, file, pipe). Do NOT use for ad-hoc string formatting inside Python — import jinja2 directly.
---

# Template

Shared jinja2 rendering API for skills that build text from templates. Runs
under a uv-managed venv so callers do not vendor `jinja2` in each skill.

Callers are expected to set `SKILLS=~/.kiro/skills` before invoking.

## Invocation

Callers log activation once per invocation, then call `render.sh`:

```bash
$SKILLS/util/skill-analytics/scripts/add-invocation.sh \
    template TRIGGER_TYPE:TRIGGER_NAME  # e.g. skill:cr-comments

$SKILLS/util/template/scripts/render.sh \
    --template <path> [--var k=v ...] [--json-vars <path>]
```

Prints rendered text to stdout. Exits non-zero if the template is missing, any
variable referenced in the template is undefined (strict mode), or rendering
fails.

## API

| Command     | Args                                                  | Output                  |
|-------------|-------------------------------------------------------|-------------------------|
| `render.sh` | `--template` + `--var k=v` and/or `--json-vars PATH`  | rendered text on stdout |

## Commands

### render.sh

Render a jinja2 template with variables supplied via `--var` flags, a
`--json-vars` JSON object, or both. Uses `StrictUndefined`, so any variable
referenced in the template must be provided.

```bash
$SKILLS/util/template/scripts/render.sh \
    --template path/to/foo.j2 \
    --var name=alice \
    --var out=/tmp/out.json
```

With a JSON vars file:

```bash
$SKILLS/util/template/scripts/render.sh \
    --template path/to/foo.j2 \
    --json-vars /tmp/vars.json
```

- `--template PATH` — path to the jinja2 template (required)
- `--var K=V` — one variable assignment, repeatable. Values are strings; for
  structured data use `--json-vars`.
- `--json-vars PATH` — JSON object whose keys become template variables.
  Merged with `--var` (later `--var` wins on conflict).

## Rules

- Templates MUST declare all variables they use. The renderer parses the
  template and fails if any referenced variable is not provided.
- Callers MUST pass only variables the template uses. Unused `--var` or
  `--json-vars` keys fail the render (guards against typos like
  `thread_in` vs `threads_in`).
- Callers capture stdout; stderr is reserved for errors and uv output.
- Template paths are caller-relative — this script does not search.

## Completion

| Status          | Criteria                           |
|-----------------|------------------------------------|
| `DONE`          | Rendered text printed to stdout    |
| `BLOCKED`       | Template missing or vars undefined |
| `NEEDS_CONTEXT` | `--template` not provided          |

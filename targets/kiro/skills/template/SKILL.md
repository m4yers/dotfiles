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
$SKILLS/home/skill-analytics/scripts/add-invocation.sh \
    template TRIGGER_TYPE:TRIGGER_NAME  # e.g. skill:cr-comments

$SKILLS/home/template/scripts/render.sh \
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
$SKILLS/home/template/scripts/render.sh \
    --template path/to/foo.j2 \
    --var name=alice \
    --var out=/tmp/out.json
```

With a JSON vars file:

```bash
$SKILLS/home/template/scripts/render.sh \
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

## Pitfalls

### `{% set %}` outside blocks is dead code under `{% extends %}`

Jinja2 inheritance changes execution: only the child's `{% block %}`
overrides run. Statements at the top level of the child — outside any
block — are parsed but never executed. That includes `{% set %}`,
`{% if %}`, and any other tag.

Symptom under this skill: the `find_undeclared_variables` pre-check
reports the set-target as missing, and the renderer exits with:

```
ERROR: template variables not provided: <var>
```

The error implies "you forgot to pass `<var>` in `--json-vars`" — but
the real cause is that `{% set <var> %}` was placed where it never
runs.

**Wrong** (sets at top level run nowhere):

```jinja
{% extends 'base.j2' %}

{% set tier = 'fast' if quintet.media == 'paper' else 'slow' %}

{% block body %}
Plan: {{ tier }}
{% endblock %}
```

**Right** (sets live inside the block that consumes them):

```jinja
{% extends 'base.j2' %}

{% block body %}
{% set tier = 'fast' if quintet.media == 'paper' else 'slow' %}
Plan: {{ tier }}
{% endblock %}
```

If multiple blocks need the same value, either repeat the `{% set %}`
in each block or put a `{% macro %}` in a shared base/partial and
import it.

### Leading-comment whitespace leaks into output

Jinja's plain `{# ... #}` comments swallow the comment body but emit
the trailing newline. A template starting with a doc comment will
therefore render with a blank first line:

```
   ← blank
---
type: keyword
```

If the consumer parses frontmatter strictly (e.g. requires `---` on
line 1) the file will be rejected. Use whitespace-controlled
delimiters (`{#- ... -#}`) or have the caller `lstrip()` the rendered
output.

### Cross-skill `{% include %}` requires every partial dir on `--include-dir`

`render.sh` resolves bare-filename includes against the
`--include-dir` list and nothing else. Templates that pull in
partials owned by another skill — e.g. the shared security frame at
`secure-llm/templates/security-frame.md.j2` — fail with:

```
ERROR: included template not found: 'security-frame.md.j2'
```

unless the caller passes that other skill's `templates/` dir too.
Production callers usually wire this correctly; the trap shows up in
ad-hoc smoke tests where the developer assumes `--include-dir =
<my-skill>/templates` is enough.

**Convention:** every directory whose `*.j2` files are referenced by
bare-filename `{% include %}` must be passed as a separate
`--include-dir`. Order matters only on name collisions (first match
wins), so list the most-specific dir first.

```bash
$SKILLS/home/template/scripts/render.sh \
    --template extractors/summary/judge.j2 \
    --include-dir <my-skill>/templates \
    --include-dir <secure-llm>/templates \
    --json-vars vars.json
```

If your template depends on a cross-skill partial, document that
dependency next to your `--include-dir` flags so future maintainers
do not have to grep for every `{% include %}` to reconstruct the
search path.

## Completion

| Status          | Criteria                           |
|-----------------|------------------------------------|
| `DONE`          | Rendered text printed to stdout    |
| `BLOCKED`       | Template missing or vars undefined |
| `NEEDS_CONTEXT` | `--template` not provided          |

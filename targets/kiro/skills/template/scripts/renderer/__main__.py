"""Render a jinja2 template with CLI-supplied variables.

Default mode (no ``--include-dir``):
  - Loads template content via ``open()`` and renders via
    ``Environment.from_string`` — same behavior as before.
  - Validates undeclared and unused variables strictly.

Loader mode (``--include-dir`` supplied, repeatable):
  - Builds a ``FileSystemLoader`` rooted at the given directories so
    ``{% include 'foo.j2' %}`` resolves correctly.
  - Resolves the ``--template`` path against the include dirs.
  - Walks ``{% include %}`` references recursively and validates
    undeclared/unused variables across the full include tree.
  - Honours optional ``--trim-blocks`` and ``--lstrip-blocks``.

Both modes use ``StrictUndefined`` and ``keep_trailing_newline``.
"""
import argparse
import json
import sys
from pathlib import Path

import jinja2
from jinja2 import meta


def _load_vars(args):
    variables = {}
    if args.json_vars:
        with open(args.json_vars) as f:
            loaded = json.load(f)
        if not isinstance(loaded, dict):
            sys.exit("ERROR: --json-vars must be a JSON object")
        variables.update(loaded)
    if args.yaml_vars:
        import yaml as _yaml
        with open(args.yaml_vars) as f:
            loaded = _yaml.safe_load(f)
        if not isinstance(loaded, dict):
            sys.exit("ERROR: --yaml-vars must be a YAML mapping")
        variables.update(loaded)
    for kv in args.var:
        if "=" not in kv:
            sys.exit(f"ERROR: --var expects K=V, got {kv!r}")
        k, v = kv.split("=", 1)
        variables[k] = v
    return variables


def _all_referenced_vars(env, tpl_text, seen=None):
    """Recursively collect every variable referenced by a template
    AND any templates it ``{% include %}``s. Returns the union as a
    set of names."""
    seen = seen if seen is not None else set()
    ast = env.parse(tpl_text)
    referenced = set(meta.find_undeclared_variables(ast))
    for ref in meta.find_referenced_templates(ast):
        # ``meta.find_referenced_templates`` yields ``None`` for
        # dynamic includes (``{% include some_var %}``); skip those.
        if ref is None or ref in seen:
            continue
        seen.add(ref)
        try:
            sub_src, _, _ = env.loader.get_source(env, ref)
        except jinja2.TemplateNotFound:
            sys.exit(f"ERROR: included template not found: {ref!r}")
        referenced |= _all_referenced_vars(env, sub_src, seen)
    return referenced


def _resolve_template_path(template_arg, include_dirs):
    """Resolve ``--template`` against ``--include-dir`` roots.

    Returns the loader-relative path (forward-slash POSIX form) of
    the template within one of the include directories. Exits if
    the template is not under any include dir.
    """
    tpl_abs = Path(template_arg).resolve()
    for d in include_dirs:
        d_abs = Path(d).resolve()
        try:
            rel = tpl_abs.relative_to(d_abs)
        except ValueError:
            continue
        return rel.as_posix()
    sys.exit(
        f"ERROR: --template {template_arg} is not under any "
        f"--include-dir: {include_dirs}"
    )


def main():
    p = argparse.ArgumentParser(prog="render")
    p.add_argument("--template", required=True)
    p.add_argument("--var", action="append", default=[], metavar="K=V",
                   help="variable assignment, repeatable")
    p.add_argument("--json-vars",
                   help="JSON file whose keys become variables")
    p.add_argument("--yaml-vars",
                   help="YAML file whose top-level mapping keys "
                        "become variables. Equivalent to --json-vars "
                        "but in YAML form; native types preserved on "
                        "load (dicts/lists stay structured).")
    p.add_argument("--include-dir", action="append", default=[],
                   metavar="PATH",
                   help="search directory for {% include %} resolution; "
                        "repeatable. Enables loader mode.")
    p.add_argument("--trim-blocks", action="store_true",
                   help="strip newline after block tags (loader mode)")
    p.add_argument("--lstrip-blocks", action="store_true",
                   help="strip leading whitespace from block tags "
                        "(loader mode)")
    p.add_argument("--allow-unused", action="store_true",
                   help="do not fail when --var/--json-vars include "
                        "keys not referenced by the template. The "
                        "strict-undefined check still fires. Use when "
                        "callers pass a deliberate superset of vars "
                        "across many templates (e.g. dispatch-style "
                        "rendering); not for hand-typed invocations.")
    args = p.parse_args()

    variables = _load_vars(args)

    if args.include_dir:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                [str(Path(d).resolve()) for d in args.include_dir]),
            undefined=jinja2.StrictUndefined,
            keep_trailing_newline=True,
            trim_blocks=args.trim_blocks,
            lstrip_blocks=args.lstrip_blocks,
        )
        rel = _resolve_template_path(args.template, args.include_dir)
        try:
            template = env.get_template(rel)
            tpl_text, _, _ = env.loader.get_source(env, rel)
        except jinja2.TemplateNotFound:
            sys.exit(f"ERROR: template not found: {args.template}")
    else:
        with open(args.template) as f:
            tpl_text = f.read()
        env = jinja2.Environment(undefined=jinja2.StrictUndefined,
                                 keep_trailing_newline=True)
        template = env.from_string(tpl_text)

    referenced = _all_referenced_vars(env, tpl_text)

    missing = referenced - variables.keys()
    if missing:
        sys.exit(f"ERROR: template variables not provided: "
                 f"{', '.join(sorted(missing))}")

    unused = variables.keys() - referenced
    if unused and not args.allow_unused:
        sys.exit(f"ERROR: variables not used by template: "
                 f"{', '.join(sorted(unused))}")

    try:
        sys.stdout.write(template.render(**variables))
    except jinja2.UndefinedError as e:
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()

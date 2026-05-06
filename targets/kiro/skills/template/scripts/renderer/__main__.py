"""Render a jinja2 template with CLI-supplied variables.

Validates:
  - Every variable referenced in the template has a value (StrictUndefined).
  - Every --var / --json-vars key is actually used by the template (catches
    typos like `thread_in` vs `threads_in`).
"""
import argparse
import json
import sys

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
    for kv in args.var:
        if "=" not in kv:
            sys.exit(f"ERROR: --var expects K=V, got {kv!r}")
        k, v = kv.split("=", 1)
        variables[k] = v
    return variables


def main():
    p = argparse.ArgumentParser(prog="render")
    p.add_argument("--template", required=True)
    p.add_argument("--var", action="append", default=[], metavar="K=V",
                   help="variable assignment, repeatable")
    p.add_argument("--json-vars",
                   help="JSON file whose keys become variables")
    args = p.parse_args()

    variables = _load_vars(args)

    with open(args.template) as f:
        tpl_text = f.read()

    env = jinja2.Environment(undefined=jinja2.StrictUndefined,
                             keep_trailing_newline=True)
    ast = env.parse(tpl_text)
    referenced = meta.find_undeclared_variables(ast)

    missing = referenced - variables.keys()
    if missing:
        sys.exit(f"ERROR: template variables not provided: "
                 f"{', '.join(sorted(missing))}")

    unused = variables.keys() - referenced
    if unused:
        sys.exit(f"ERROR: variables not used by template: "
                 f"{', '.join(sorted(unused))}")

    try:
        sys.stdout.write(env.from_string(tpl_text).render(**variables))
    except jinja2.UndefinedError as e:
        sys.exit(f"ERROR: {e}")


if __name__ == "__main__":
    main()

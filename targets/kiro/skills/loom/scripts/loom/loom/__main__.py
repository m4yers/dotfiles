'''CLI entry point for loom.

Usage:
  python -m loom output init <workdir> --task <id>
  python -m loom output add  <workdir> --task <id> --set path=value [--set ...]

This is intentionally minimal: loom is a library, not a control plane.
The CLI exists so sub-agents (LLM tasks) can write schema-validated
output.yaml files via shell calls.
'''
from __future__ import annotations

import argparse
from pathlib import Path

from loom import builders


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='loom', description='loom CLI')
    sub = p.add_subparsers(dest='cmd', required=True)

    output = sub.add_parser('output', help='write task output.yaml')
    out_sub = output.add_subparsers(dest='output_cmd', required=True)

    p_init = out_sub.add_parser(
        'init', help='initialize output.yaml for a task')
    p_init.add_argument('workdir', type=Path,
                        help='loom workdir containing plan.yaml')
    p_init.add_argument('--task', required=True,
                        help='task id whose output to initialize')

    p_add = out_sub.add_parser(
        'add', help='set fields in output.yaml and validate')
    p_add.add_argument('workdir', type=Path,
                       help='loom workdir containing plan.yaml')
    p_add.add_argument('--task', required=True,
                       help='task id whose output to update')
    p_add.add_argument('--set', dest='set_pairs', action='append',
                       default=[], required=True, metavar='path=value',
                       help='dotted path = value (repeatable)')

    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == 'output':
        if args.output_cmd == 'init':
            builders.cmd_init(args.workdir.expanduser().resolve(),
                              args.task)
            return 0
        if args.output_cmd == 'add':
            builders.cmd_add(args.workdir.expanduser().resolve(),
                             args.task, args.set_pairs)
            return 0
    raise SystemExit(2)


if __name__ == '__main__':
    main()

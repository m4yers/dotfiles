'''CLI entry point for loom.

Subcommands:
  output init <workdir> --task <id>
  output add  <workdir> --task <id> --set path=value [--set ...]
  visualise <workdir>            [--no-when] [--no-loops] [--ascii-only] [-o FILE]
  visualise --plan <plan.yaml>   ... same flags
'''
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from loom import builders
from loom.engine.models import LoomPlan
from loom.visualise import visualise, visualise_workdir


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='loom', description='loom CLI')
    sub = p.add_subparsers(dest='cmd', required=True)

    # ---- output ----
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

    # ---- visualise ----
    p_viz = sub.add_parser(
        'visualise',
        help='render a plan as a dependents-first ASCII rail')
    src = p_viz.add_mutually_exclusive_group(required=True)
    src.add_argument('workdir', nargs='?', type=Path,
                     help='loom workdir containing plan.yaml')
    src.add_argument('--plan', type=Path,
                     help='path to a plan.yaml file directly')
    p_viz.add_argument('--no-when', action='store_true',
                       help='omit when: predicate annotations')
    p_viz.add_argument('--no-loops', action='store_true',
                       help='omit loop-latch annotations')
    p_viz.add_argument('--ascii-only', action='store_true',
                       help='strict 7-bit ASCII output')
    p_viz.add_argument('-o', '--output', type=Path, default=None,
                       help='write to file instead of stdout')

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
    if args.cmd == 'visualise':
        text = _run_visualise(args)
        if args.output:
            args.output.write_text(text + '\n', encoding='utf-8')
        else:
            sys.stdout.write(text)
            sys.stdout.write('\n')
        return 0
    raise SystemExit(2)


def _run_visualise(args) -> str:
    kwargs = dict(
        show_when=not args.no_when,
        show_loops=not args.no_loops,
        ascii_only=args.ascii_only,
    )
    if args.workdir:
        return visualise_workdir(args.workdir, **kwargs)
    plan = LoomPlan.from_yaml(args.plan)
    return visualise(plan, **kwargs)


if __name__ == '__main__':
    main()

"""argparse CLI dispatcher for `python -m loom`.

Subcommands mirror the API table in SKILL.md exactly. Non-zero exit
on any LoomPlanError; failure messages carry the class remedy. The
``runtime init`` / ``runtime next`` / ``runtime complete`` loop is
the primary caller interface; other subcommands are scaffolding and
diagnostics.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


class _SetAssignmentAction(argparse.Action):
    """Collect ``--set`` / ``--set-json`` into ONE ordered list.

    Each entry is ``(is_json, "path=value")``. A single shared list
    preserves CLI order across the two flags, so mixed invocations that
    build list elements incrementally (``items[]`` then ``items[-1].x``)
    apply exactly as written.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None) or []
        items.append((option_string == "--set-json", values))
        setattr(namespace, self.dest, items)


def main(argv: list[str] | None = None) -> int:
    """Dispatch a CLI invocation."""
    parser = argparse.ArgumentParser(prog="loom")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_task = sub.add_parser("task")
    p_task_sub = p_task.add_subparsers(dest="task_cmd", required=True)
    p_task_new = p_task_sub.add_parser("new")
    p_task_new.add_argument("name")
    p_task_new.add_argument("--loom-root", type=Path, default=Path.cwd() / "loom")
    p_task_io = p_task_sub.add_parser("io-python")
    p_task_io.add_argument("name")
    p_task_io.add_argument("--loom-root", type=Path, default=Path.cwd() / "loom")

    p_graph = sub.add_parser("graph")
    p_graph_sub = p_graph.add_subparsers(dest="graph_cmd", required=True)
    p_graph_new = p_graph_sub.add_parser("new")
    p_graph_new.add_argument("--loom-root", type=Path, default=Path.cwd() / "loom")

    p_runtime = sub.add_parser("runtime")
    p_runtime_sub = p_runtime.add_subparsers(dest="runtime_cmd", required=True)
    p_init = p_runtime_sub.add_parser("init")
    p_init.add_argument("workdir", type=Path, nargs="?", default=None)
    p_init.add_argument("--loom-root", type=Path, required=True)
    p_init.add_argument("--set", dest="assignments", action="append", default=[])

    p_next = p_runtime_sub.add_parser("next")
    p_next.add_argument("workdir", type=Path)

    p_complete = p_runtime_sub.add_parser("complete")
    p_complete.add_argument("workdir", type=Path)
    p_complete.add_argument("task_address")

    p_fail = p_runtime_sub.add_parser("fail")
    p_fail.add_argument("workdir", type=Path)
    p_fail.add_argument("task_address")
    p_fail.add_argument("--message", required=True)

    p_reset = p_runtime_sub.add_parser("reset")
    p_reset.add_argument("workdir", type=Path)
    p_reset.add_argument("task_address")

    p_status = p_runtime_sub.add_parser("status")
    p_status.add_argument("workdir", type=Path)

    p_output = sub.add_parser("output")
    p_output_sub = p_output.add_subparsers(dest="output_cmd", required=True)
    p_out_init = p_output_sub.add_parser("init")
    p_out_init.add_argument("workdir", type=Path)
    p_out_init.add_argument("--task", required=True)
    p_out_add = p_output_sub.add_parser("add")
    p_out_add.add_argument("workdir", type=Path)
    p_out_add.add_argument("--task", required=True)
    p_out_add.add_argument("--set", dest="assignments",
                           action=_SetAssignmentAction, default=[])
    p_out_add.add_argument("--set-json", dest="assignments",
                           action=_SetAssignmentAction, default=[])

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("skill_root", type=Path)
    p_validate.add_argument("--graph", type=Path, default=None,
                            help="path to a graph.yaml file directly")

    p_visualise = sub.add_parser("visualise")
    src = p_visualise.add_mutually_exclusive_group(required=True)
    src.add_argument("workdir", nargs="?", type=Path,
                     help="loom workdir containing plan.yaml")
    src.add_argument("--plan", type=Path,
                     help="path to a plan.yaml file directly")
    p_visualise.add_argument("--no-when", action="store_true",
                             help="omit when: predicate annotations")
    p_visualise.add_argument("--no-loops", action="store_true",
                             help="omit loop-latch annotations")
    p_visualise.add_argument("--ascii-only", action="store_true",
                             help="strict 7-bit ASCII output")
    p_visualise.add_argument("-o", "--output", type=Path, default=None,
                             help="write to file instead of stdout")

    args = parser.parse_args(argv)
    return _dispatch(args)


def _dispatch(args) -> int:
    from loom.errors import LoomPlanError

    try:
        if args.cmd == "task" and args.task_cmd == "new":
            from loom.scaffold import new_task

            new_task(args.loom_root, args.name)
        elif args.cmd == "task" and args.task_cmd == "io-python":
            from loom.scaffold import io_python

            io_python(args.loom_root, args.name)
        elif args.cmd == "graph" and args.graph_cmd == "new":
            from loom.scaffold import new_graph

            new_graph(args.loom_root)
        elif args.cmd == "runtime" and args.runtime_cmd == "init":
            from loom.cli_run import cmd_init

            return cmd_init(
                args.workdir,
                args.loom_root,
                assignments=args.assignments,
            )
        elif args.cmd == "runtime" and args.runtime_cmd == "next":
            from loom.cli_run import cmd_next

            return cmd_next(args.workdir)
        elif args.cmd == "runtime" and args.runtime_cmd == "complete":
            from loom.cli_run import cmd_complete

            return cmd_complete(args.workdir, args.task_address)
        elif args.cmd == "runtime" and args.runtime_cmd == "fail":
            from loom.cli_run import cmd_fail

            return cmd_fail(args.workdir, args.task_address, args.message)
        elif args.cmd == "runtime" and args.runtime_cmd == "reset":
            from loom.cli_run import cmd_reset

            return cmd_reset(args.workdir, args.task_address)
        elif args.cmd == "runtime" and args.runtime_cmd == "status":
            from loom.cli_run import cmd_status

            return cmd_status(args.workdir)
        elif args.cmd == "output" and args.output_cmd == "init":
            from loom.builders import output_init

            output_init(args.workdir, args.task)
        elif args.cmd == "output" and args.output_cmd == "add":
            from loom.builders import output_add

            output_add(args.workdir, args.task, args.assignments)
        elif args.cmd == "validate":
            _validate_cli(args)
        elif args.cmd == "visualise":
            _run_visualise(args)
    except LoomPlanError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def _run_visualise(args) -> None:
    """Render the plan and write to stdout or ``-o FILE``.

    Positional ``workdir`` loads ``<workdir>/plan.yaml`` via
    ``read_plan_yaml``; ``--plan`` accepts an arbitrary plan.yaml path.
    """
    import yaml

    from loom.engine.store import _dict_to_plan
    from loom.visualise import visualise, visualise_workdir

    kwargs = dict(
        show_when=not args.no_when,
        show_loops=not args.no_loops,
        ascii_only=args.ascii_only,
    )
    if args.workdir:
        text = visualise_workdir(args.workdir, **kwargs)
    else:
        plan_path = Path(args.plan).expanduser()
        doc = yaml.safe_load(plan_path.read_text()) or {}
        plan = _dict_to_plan(doc)
        text = visualise(plan, **kwargs)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def _validate_cli(args) -> None:
    from loom.plan import from_graph_yaml
    from loom._lifecycle import _static_validate
    from loom.engine.inline import expand_subgraphs

    plan = from_graph_yaml(args.skill_root)
    composed = expand_subgraphs(plan)
    _static_validate(composed, pinning_graph=args.skill_root / "graph.yaml")


if __name__ == "__main__":
    sys.exit(main())

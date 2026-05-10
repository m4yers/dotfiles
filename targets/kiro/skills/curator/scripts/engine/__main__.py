#!/usr/bin/env python3
"""Curator engine — argparse dispatcher.

All curator ops route through here. No LLM calls inside.
The orchestrator (main Kiro session) and sub-agents drive
reasoning; this module provides I/O primitives.

Usage:
  python -m engine fetch <url-or-path>
  python -m engine convert <path>
  python -m engine context
  python -m engine page write   <vault-path> --body-file X --frontmatter-file Y
  python -m engine page extend  <vault-path> --section S --body-file X [--mode append|replace]
  python -m engine page read    <vault-path> [--section S]
  python -m engine page stubs   [--folder F]
  python -m engine page orphans
  python -m engine page verify-batch <approved-json>
  python -m engine page apply-plan <plan-json>
  python -m engine lint         [--scope F]
  python -m engine commit       <message>
  python -m engine recent       [-n 20]
  python -m engine sweep        [<workdir>] [--all]
"""
import argparse
import json
import sys

from engine import context, fetch, convert, git_ops, lint, pages, validate, workdir


def _emit(obj):
    """Print JSON to stdout, one line."""
    print(json.dumps(obj, ensure_ascii=False))


def _fail(msg, **extra):
    print(json.dumps({"error": msg, **extra}), file=sys.stderr)
    sys.exit(1)


def cmd_fetch(args):
    result = fetch.fetch(args.url_or_path, topic=args.topic)
    _emit(result)


def cmd_convert(args):
    result = convert.convert(args.path)
    _emit(result)


def cmd_context(args):
    result = context.build_context(types=args.types.split(",") if args.types else None)
    _emit(result)


def cmd_page_write(args):
    result = pages.write(
        vault_path=args.vault_path,
        body_file=args.body_file,
        frontmatter_file=args.frontmatter_file,
        allow_uncited=args.allow_uncited,
    )
    _emit(result)


def cmd_page_extend(args):
    result = pages.extend(
        vault_path=args.vault_path,
        section=args.section,
        body_file=args.body_file,
        mode=args.mode,
        frontmatter_delta_file=args.frontmatter_delta_file,
    )
    _emit(result)


def cmd_page_read(args):
    result = pages.read(args.vault_path, section=args.section)
    _emit(result)


def cmd_page_stubs(args):
    result = pages.stubs(folder=args.folder)
    _emit(result)


def cmd_page_orphans(args):
    result = pages.orphans()
    _emit(result)


def cmd_page_verify_batch(args):
    result = pages.verify_batch(args.approved_json, composed_json_path=args.composed)
    _emit(result)
    if not result.get("ok"):
        sys.exit(1)


def cmd_page_materialize(args):
    result = pages.materialize(args.approved_json, composed_json_path=args.composed)
    _emit(result)


def cmd_page_apply_plan(args):
    result = pages.apply_plan(args.plan_json)
    _emit(result)
    if not result.get("ok"):
        sys.exit(1)


def cmd_lint(args):
    result = lint.lint(scope=args.scope)
    _emit(result)


def cmd_commit(args):
    result = git_ops.commit(args.message)
    _emit(result)


def cmd_recent(args):
    result = git_ops.recent(n=args.n)
    _emit(result)


def cmd_sweep(args):
    result = workdir.sweep(path=args.path, all_stale=args.all)
    _emit(result)


def cmd_validate(args):
    result = validate.validate_extractors(args.workdir)
    _emit(result)
    if not result.get("ok"):
        sys.exit(1)


def cmd_validate_schema(args):
    result = validate.validate_schema(args.kind, args.file)
    _emit(result)
    if not result.get("ok"):
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(prog="curator", description="Curator engine.")
    sub = p.add_subparsers(dest="cmd", required=True)

    # ── fetch ────────────────────────────────────────
    s = sub.add_parser("fetch", help="Acquire a source")
    s.add_argument("url_or_path")
    s.add_argument("--topic", default=None)
    s.set_defaults(func=cmd_fetch)

    # ── convert ──────────────────────────────────────
    s = sub.add_parser("convert", help="Produce transient source.md in workdir")
    s.add_argument("path", help="Vault-relative or absolute path to source")
    s.set_defaults(func=cmd_convert)

    # ── context ──────────────────────────────────────
    s = sub.add_parser("context", help="Vault state for extractors")
    s.add_argument(
        "--types",
        default=None,
        help="Comma-separated: keywords,people,models,synthesis",
    )
    s.set_defaults(func=cmd_context)

    # ── page ─────────────────────────────────────────
    pp = sub.add_parser("page", help="Page operations")
    psub = pp.add_subparsers(dest="page_cmd", required=True)

    s = psub.add_parser("write", help="Create or overwrite a page")
    s.add_argument("vault_path")
    s.add_argument("--body-file", required=True)
    s.add_argument("--frontmatter-file", required=True)
    s.add_argument("--allow-uncited", action="store_true", default=False)
    s.set_defaults(func=cmd_page_write)

    s = psub.add_parser("extend", help="Extend a page with a new or existing section")
    s.add_argument("vault_path")
    s.add_argument("--section", required=True)
    s.add_argument("--body-file", required=True)
    s.add_argument("--mode", choices=["append", "replace"], default="append")
    s.add_argument("--frontmatter-delta-file", default=None)
    s.set_defaults(func=cmd_page_extend)

    s = psub.add_parser("read", help="Read a page (full or section)")
    s.add_argument("vault_path")
    s.add_argument("--section", default=None)
    s.set_defaults(func=cmd_page_read)

    s = psub.add_parser("stubs", help="List 0-byte or minimal pages")
    s.add_argument("--folder", default=None)
    s.set_defaults(func=cmd_page_stubs)

    s = psub.add_parser("orphans", help="List pages not linked from anywhere")
    s.set_defaults(func=cmd_page_orphans)

    s = psub.add_parser("verify-batch", help="Verify all writes in approved.json landed")
    s.add_argument("approved_json")
    s.add_argument("--composed", default=None,
                   help="composed.json path; defaults to sibling of approved.json")
    s.set_defaults(func=cmd_page_verify_batch)

    s = psub.add_parser("materialize",
                        help="Expand approved proposals into body/frontmatter files + plan")
    s.add_argument("approved_json")
    s.add_argument("--composed", default=None,
                   help="composed.json path; defaults to sibling of approved.json")
    s.set_defaults(func=cmd_page_materialize)

    s = psub.add_parser("apply-plan",
                        help="Execute every entry in plan.json via write/extend")
    s.add_argument("plan_json")
    s.set_defaults(func=cmd_page_apply_plan)

    # ── lint ─────────────────────────────────────────
    s = sub.add_parser("lint", help="Vault health check")
    s.add_argument("--scope", default="all")
    s.set_defaults(func=cmd_lint)

    # ── commit ───────────────────────────────────────
    s = sub.add_parser("commit", help="Git commit curator-owned paths")
    s.add_argument("message")
    s.set_defaults(func=cmd_commit)

    # ── recent ───────────────────────────────────────
    s = sub.add_parser("recent", help="Recent curator commits")
    s.add_argument("-n", type=int, default=20)
    s.set_defaults(func=cmd_recent)

    # ── sweep ────────────────────────────────────────
    s = sub.add_parser("sweep", help="Delete a workdir or all stale workdirs")
    s.add_argument("path", nargs="?", default=None)
    s.add_argument("--all", action="store_true", default=False)
    s.set_defaults(func=cmd_sweep)

    # ── validate ─────────────────────────────────────
    s = sub.add_parser("validate", help="Validate all extractor JSON outputs in a workdir")
    s.add_argument("workdir")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("validate-schema",
                       help="Validate a single pipeline artifact (composed/approved)")
    s.add_argument("kind", choices=["composed", "approved"])
    s.add_argument("file")
    s.set_defaults(func=cmd_validate_schema)

    args = p.parse_args()
    try:
        args.func(args)
    except FileNotFoundError as e:
        _fail(f"not found: {e}")
    except ValueError as e:
        _fail(str(e))
    except PermissionError as e:
        _fail(f"permission denied: {e}")


if __name__ == "__main__":
    main()

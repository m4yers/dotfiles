#!/usr/bin/env python3
"""Curator vault tool — argparse dispatcher.

Scope: page CRUD, materialize + apply-plan + verify-batch, context
(read vault state for extractors), lint (vault health), commit
(git), recent. No workdir lifecycle, no source acquisition, no
workdir JSON builders — those live in the disk and source tools.

Every canonical JSON artifact this tool writes (plan.json) goes
through an inline atomic schema-gated write.
"""
import argparse
import json
import sys
from pathlib import Path

import jsonschema

from vault import context, git_ops, lint, pages

# Context schema lives with the disk-tool schemas since that package
# owns every canonical curator JSON shape.
_CONTEXT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "disk" / "schemas" / "context.schema.json"
)


def _emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


def _fail(msg, **extra):
    print(json.dumps({"error": msg, **extra}), file=sys.stderr)
    sys.exit(1)


# ── context / lint / git ──────────────────────────────────

def cmd_context(args):
    result = context.build_context(
        types=args.types.split(",") if args.types else None)
    schema = json.loads(_CONTEXT_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=result, schema=schema)
    except jsonschema.ValidationError as e:
        _fail(f"context schema violation: {e.message}")
    _emit(result)


def cmd_lint(args):
    _emit(lint.lint(scope=args.scope))


def cmd_commit(args):
    _emit(git_ops.commit(args.message))


def cmd_recent(args):
    _emit(git_ops.recent(n=args.n))


# ── page ─────────────────────────────────────────────────

def cmd_page_write(args):
    _emit(pages.write(vault_path=args.vault_path,
                      body_file=args.body_file,
                      frontmatter_file=args.frontmatter_file,
                      allow_uncited=args.allow_uncited))


def cmd_page_extend(args):
    _emit(pages.extend(vault_path=args.vault_path, section=args.section,
                       body_file=args.body_file, mode=args.mode,
                       frontmatter_delta_file=args.frontmatter_delta_file))


def cmd_page_read(args):
    _emit(pages.read(args.vault_path, section=args.section))


def cmd_page_stubs(args):
    _emit(pages.stubs(folder=args.folder))


def cmd_page_orphans(args):
    _emit(pages.orphans())


def cmd_page_verify_batch(args):
    result = pages.verify_batch(args.approved_json,
                                composed_json_path=args.composed)
    _emit(result)
    if not result.get("ok"):
        sys.exit(1)


def cmd_page_materialize(args):
    _emit(pages.materialize(args.approved_json,
                            composed_json_path=args.composed))


def cmd_page_apply_plan(args):
    result = pages.apply_plan(args.plan_json)
    _emit(result)
    if not result.get("ok"):
        sys.exit(1)


# ── argparse wiring ──────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="vault", description="Curator vault tool.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("context", help="Vault state for extractors")
    s.add_argument("--types", default=None,
                   help="Comma-separated: keywords,people,models,synthesis")
    s.set_defaults(func=cmd_context)

    s = sub.add_parser("lint", help="Vault health check")
    s.add_argument("--scope", default="all")
    s.set_defaults(func=cmd_lint)

    s = sub.add_parser("commit", help="Git commit curator-owned paths")
    s.add_argument("message")
    s.set_defaults(func=cmd_commit)

    s = sub.add_parser("recent", help="Recent curator commits")
    s.add_argument("-n", type=int, default=20)
    s.set_defaults(func=cmd_recent)

    pp = sub.add_parser("page", help="Page operations")
    psub = pp.add_subparsers(dest="page_cmd", required=True)

    s = psub.add_parser("write", help="Create or overwrite a page")
    s.add_argument("vault_path")
    s.add_argument("--body-file", required=True)
    s.add_argument("--frontmatter-file", required=True)
    s.add_argument("--allow-uncited", action="store_true", default=False)
    s.set_defaults(func=cmd_page_write)

    s = psub.add_parser("extend", help="Extend a page with a section")
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

    s = psub.add_parser("verify-batch",
                        help="Verify all writes in approved.json landed")
    s.add_argument("approved_json")
    s.add_argument("--composed", default=None)
    s.set_defaults(func=cmd_page_verify_batch)

    s = psub.add_parser("materialize",
                        help="Expand approved proposals into body/frontmatter files + plan")
    s.add_argument("approved_json")
    s.add_argument("--composed", default=None)
    s.set_defaults(func=cmd_page_materialize)

    s = psub.add_parser("apply-plan",
                        help="Execute every entry in plan.json via write/extend")
    s.add_argument("plan_json")
    s.set_defaults(func=cmd_page_apply_plan)

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

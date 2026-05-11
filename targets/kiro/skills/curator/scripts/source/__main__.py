#!/usr/bin/env python3
"""Curator source — argparse dispatcher.

Two operations: ``fetch`` (URL or local path → vault source file +
workdir meta) and ``convert`` (vault source file → workdir
source.md). The workdir is always supplied by the caller; the source tool
does not create or sweep workdirs.
"""
import argparse
import json
import sys
from pathlib import Path

import jsonschema

from source import convert, fetch

# Fetch envelope schema lives with the disk-tool schemas since that
# package owns every canonical curator JSON shape.
_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "disk" / "schemas" / "fetch-envelope.schema.json"
)


def _emit(obj):
    print(json.dumps(obj, ensure_ascii=False))


def _fail(msg, **extra):
    print(json.dumps({"error": msg, **extra}), file=sys.stderr)
    sys.exit(1)


def cmd_fetch(args):
    result = fetch.fetch(
        args.url_or_path,
        Path(args.workdir),
        topic=args.topic,
        media_override=args.media,
    )
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=result, schema=schema)
    except jsonschema.ValidationError as e:
        _fail(f"fetch envelope schema violation: {e.message}",
              envelope=result)
    _emit(result)
    if not result.get("ok", True):
        sys.exit(1)


def cmd_convert(args):
    _emit(convert.convert(args.path, args.workdir))


def main():
    p = argparse.ArgumentParser(prog="source",
                                description="Curator source tool.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("fetch", help="Acquire a source (URL or local path)")
    s.add_argument("url_or_path")
    s.add_argument("--workdir", required=True,
                   help="Workdir (create via `disk.sh workdir create`)")
    s.add_argument("--topic", default=None)
    s.add_argument("--media", default=None,
                   help="Override handler-classified content_type "
                        "(paper|book|article|lecture|talk|podcast|"
                        "video|movie|audio|unknown). Use when the "
                        "handler's default does not match the "
                        "source's nature (e.g. a book delivered as "
                        "a PDF).")
    s.set_defaults(func=cmd_fetch)

    s = sub.add_parser("convert",
                       help="Write <workdir>/source.md from a vault source file")
    s.add_argument("path", help="Vault-relative or absolute path to source")
    s.add_argument("--workdir", required=True)
    s.set_defaults(func=cmd_convert)

    args = p.parse_args()
    try:
        args.func(args)
    except FileNotFoundError as e:
        _fail(f"not found: {e}")
    except ValueError as e:
        _fail(str(e))


if __name__ == "__main__":
    main()

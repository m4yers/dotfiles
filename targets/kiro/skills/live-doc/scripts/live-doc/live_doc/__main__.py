"""CLI entry for the live-doc skill.

Two subcommands: `create` scaffolds a new doc and opens it in the
editor; `ingest` is the refresh pipeline's entry point and invokes
`loom runtime init`, printing the workdir path on stdout.
"""
from __future__ import annotations

import argparse
import sys

from live_doc import create, ingest


def main() -> None:
    parser = argparse.ArgumentParser(prog="live-doc")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="scaffold a new live doc")
    p_create.add_argument("--path", required=True,
                          help="target vault path, e.g. "
                               "<vault>/work/live/live-<name>.md")

    p_ingest = sub.add_parser("ingest", help="refresh pipeline entry")
    p_ingest.add_argument("--path", required=True,
                          help="existing live-doc file to refresh")

    args = parser.parse_args()
    if args.cmd == "create":
        create.run(args.path)
    elif args.cmd == "ingest":
        ingest.run(args.path)
    else:  # pragma: no cover
        parser.error(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())

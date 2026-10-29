"""CLI entry for the live-journal skill.

Six subcommands dispatch to the create, open, and topic/section/appendix
mutation modules.
"""
from __future__ import annotations

import argparse
import sys

from live_journal import create, open_journal, topic_edits


def main() -> None:
    parser = argparse.ArgumentParser(prog="live-journal")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="scaffold a new live journal")
    p_create.add_argument(
        "--path", required=True,
        help="target vault path, e.g. "
             "<vault>/work/live-journal/live-journal-<name>.md",
    )

    p_open = sub.add_parser("open", help="open and summarise a live journal")
    p_open.add_argument("--path", required=True,
                        help="existing live-journal file to open")

    p_topic = sub.add_parser("topic", help="topic-level mutations")
    topic_sub = p_topic.add_subparsers(dest="topic_cmd", required=True)

    p_topic_add = topic_sub.add_parser("add", help="append a new topic")
    p_topic_add.add_argument("--path", required=True)
    p_topic_add.add_argument("--title", required=True,
                             help="new topic title")

    p_topic_status = topic_sub.add_parser(
        "status", help="flip the status marker on an existing topic",
    )
    p_topic_status.add_argument("--path", required=True)
    p_topic_status.add_argument("--title", required=True,
                                help="topic title to update")
    p_topic_status.add_argument("--status", required=True,
                                choices=("in-progress", "done"))

    p_section = sub.add_parser("section", help="sub-section mutations")
    section_sub = p_section.add_subparsers(dest="section_cmd", required=True)
    p_section_put = section_sub.add_parser(
        "put", help="upsert an H3 sub-section under a topic",
    )
    p_section_put.add_argument("--path", required=True)
    p_section_put.add_argument("--topic", required=True,
                               help="existing topic title")
    p_section_put.add_argument("--heading", required=True,
                               help="H3 sub-section heading")
    p_section_put.add_argument("--body", required=True,
                               help="file whose contents form the body")

    p_app = sub.add_parser("appendix", help="appendix mutations")
    app_sub = p_app.add_subparsers(dest="appendix_cmd", required=True)
    p_app_add = app_sub.add_parser(
        "add", help="embed or replace a script in `## Appendix`",
    )
    p_app_add.add_argument("--path", required=True)
    p_app_add.add_argument("--name", required=True,
                           help="script name (unique within appendix)")
    p_app_add.add_argument("--source", required=True,
                           help="file whose contents form the script body")

    args = parser.parse_args()
    if args.cmd == "create":
        create.run(args.path)
    elif args.cmd == "open":
        open_journal.run(args.path)
    elif args.cmd == "topic" and args.topic_cmd == "add":
        topic_edits.topic_add(args.path, args.title)
    elif args.cmd == "topic" and args.topic_cmd == "status":
        topic_edits.topic_status(args.path, args.title, args.status)
    elif args.cmd == "section" and args.section_cmd == "put":
        topic_edits.section_put(
            args.path, args.topic, args.heading, args.body,
        )
    elif args.cmd == "appendix" and args.appendix_cmd == "add":
        topic_edits.appendix_add(args.path, args.name, args.source)
    else:  # pragma: no cover
        parser.error(f"unknown command: {args.cmd}")


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Show, list, count, resolve, or delete pending retro items.

Items are sorted by severity, then area, then action, then file name. The
number N shown in the dashboard is the 1-based position in that order;
--list, --path and --delete use the same numbering.

Modes (default: colored dashboard table):
  --list          JSON array on stdout, one object per item:
                    id        int   dashboard number N
                    path      str   absolute path of the JSON file
                    title     str
                    area      str   skill|steering|prompt ("unknown" if absent)
                    action    str   new|update ("?" if absent)
                    severity  str   high|medium|low
                    target    str|null
                    detail    str|null
                    evidence  str|null
  --count         number of valid pending items on stdout
  --path N        absolute path of item N on stdout
  --delete N...   delete items N... (numbers resolved against one snapshot);
                  prints "deleted: <path>: <title>" per file

Unreadable or malformed files are reported as "error: <file>: <reason>" on
stderr, skipped, and make the script exit 1 after the requested output.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ANSI escape codes
RED = "\033[31m"
YEL = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RST = "\033[0m"

# Sort order: high first, medium second, low third; 9 = unknown severity sorts last
SEVERITY_ORDER = {"high": 1, "medium": 2, "low": 3}
SEVERITY_STYLE = {
    "high": (RED, "●"),
    "medium": (YEL, "◐"),
    "low": (DIM, "○"),
}


def normalize_target(target):
    if not target:
        return "—"
    parts = target.replace("~/.kiro/", "").rstrip("/").split("/")
    for drop in ("SKILL.md", "skills", "steering", "prompts", "dev", "diagnostics", "util"):
        while drop in parts:
            parts.remove(drop)
    name = "/".join(parts) if parts else os.path.basename(target)
    if name == "—":
        return name
    # Not str.removesuffix: this runs under the host python3, which is 3.7.
    return name[: -len(".md")] if name.endswith(".md") else name


def load_items(pending):
    """Return (items, had_errors); items are sorted dicts with an id."""
    items = []
    had_errors = False
    for f in sorted(pending.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            item = {
                "path": str(f.resolve()),
                "title": d["title"],
                "area": d.get("area", "unknown"),
                "action": d.get("action", "?"),
                "severity": d["severity"],
                "target": d.get("target"),
                "detail": d.get("detail"),
                "evidence": d.get("evidence"),
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            # ValueError covers json.JSONDecodeError and bad UTF-8.
            reason = "missing key {}".format(e) if isinstance(e, KeyError) else e
            print("error: {}: {}".format(f, reason), file=sys.stderr)
            had_errors = True
            continue
        items.append(item)
    items.sort(key=lambda r: (SEVERITY_ORDER.get(r["severity"], 9), r["area"], r["action"]))
    for i, item in enumerate(items, 1):
        item["id"] = i
    return items, had_errors


def pick(items, n):
    if n < 1 or n > len(items):
        print("error: no item #{} (have {})".format(n, len(items)), file=sys.stderr)
        sys.exit(2)
    return items[n - 1]


def delete(items, numbers, pending):
    root = pending.resolve()
    chosen = [pick(items, n) for n in dict.fromkeys(numbers)]
    for item in chosen:
        path = Path(item["path"])
        # Refuse anything that resolves outside the pending dir.
        if path.parent != root or path.suffix != ".json":
            print("error: {}: not inside {}".format(path, root), file=sys.stderr)
            sys.exit(2)
    for item in chosen:
        os.remove(item["path"])
        print("deleted: {}: {}".format(item["path"], item["title"]))


def print_table(items):
    if not items:
        print("No pending retro items.")
        return
    print(f"{BOLD}{'#':<4} {'':2} {'Area':<10} {'Action':<8} {'Target':<20} Finding{RST}")
    for item in items:
        color, icon = SEVERITY_STYLE.get(item["severity"], (RST, "?"))
        target = normalize_target(item["target"])
        print(
            f"{color}{item['id']:<4} {icon}  {item['area']:<10} {item['action']:<8} "
            f"{target:<20} {item['title']}{RST}"
        )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dir",
        default=Path.home() / ".kiro" / "retro" / "pending",
        type=Path,
        help="Path to retro pending directory",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="print items as JSON")
    mode.add_argument("--count", action="store_true", help="print item count")
    mode.add_argument("--path", type=int, metavar="N", help="print path of item N")
    mode.add_argument(
        "--delete", type=int, nargs="+", metavar="N", help="delete items N..."
    )
    args = parser.parse_args()

    if not args.dir.is_dir():
        print("error: {}: not a directory".format(args.dir), file=sys.stderr)
        sys.exit(1)

    items, had_errors = load_items(args.dir)
    if args.list:
        order = ("id", "path", "title", "area", "action", "severity", "target",
                 "detail", "evidence")
        print(json.dumps([{k: it[k] for k in order} for it in items], indent=2,
                         ensure_ascii=False))
    elif args.count:
        print(len(items))
    elif args.path is not None:
        print(pick(items, args.path)["path"])
    elif args.delete:
        delete(items, args.delete, args.dir)
    else:
        print_table(items)

    if had_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

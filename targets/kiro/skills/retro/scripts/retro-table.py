#!/usr/bin/env python3
"""Print pending retro items as a colored formatted table, sorted by severity then area."""

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
    return name.removesuffix(".md") if name != "—" else name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        default=Path.home() / ".kiro" / "retro" / "pending",
        type=Path,
        help="Path to retro pending directory",
    )
    args = parser.parse_args()

    files = sorted(args.dir.glob("*.json"))
    if not files:
        print("No pending retro items.")
        return

    rows = []
    for f in files:
        d = json.loads(f.read_text())
        sev = d["severity"]
        rows.append((
            SEVERITY_ORDER.get(sev, 9),
            sev,
            d.get("area", "unknown"),
            d.get("action", "?"),
            normalize_target(d.get("target")),
            d["title"],
        ))

    rows.sort(key=lambda r: (r[0], r[2], r[3]))

    print(f"{BOLD}{'#':<4} {'':2} {'Area':<10} {'Action':<8} {'Target':<20} Finding{RST}")
    for i, (_, sev, area, action, target, title) in enumerate(rows, 1):
        color, icon = SEVERITY_STYLE.get(sev, (RST, "?"))
        print(f"{color}{i:<4} {icon}  {area:<10} {action:<8} {target:<20} {title}{RST}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Write a retro JSON file to a target directory.

Usage:
  write-retro-item.py --dir DIR --area AREA --action ACTION \
    --severity SEVERITY --title TITLE --detail DETAIL \
    --evidence EVIDENCE [--target TARGET]

Arguments:
  --dir        Directory to write the JSON file into
  --area       skill|steering|vault|prompt
  --action     new|update
  --severity   high|medium|low
  --title      Short description
  --detail     What happened and what should change
  --evidence   Relevant conversation context
  --target     Optional short name for the target
"""
import argparse
import json
import os
import sys
from datetime import datetime

AREAS = {"skill", "steering", "vault", "prompt"}
ACTIONS = {"new", "update"}
SEVERITIES = {"high", "medium", "low"}


def main():
    p = argparse.ArgumentParser(description="Write a retro JSON item.")
    p.add_argument("--dir", required=True, help="Target directory")
    p.add_argument("--area", required=True, choices=sorted(AREAS))
    p.add_argument("--action", required=True, choices=sorted(ACTIONS))
    p.add_argument("--severity", required=True, choices=sorted(SEVERITIES))
    p.add_argument("--title", required=True)
    p.add_argument("--detail", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--target", default=None)
    args = p.parse_args()

    os.makedirs(args.dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(args.dir, f"{ts}.json")

    item = {
        "area": args.area,
        "action": args.action,
        "severity": args.severity,
        "target": args.target,
        "title": args.title,
        "detail": args.detail,
        "evidence": args.evidence,
    }

    with open(path, "w") as f:
        json.dump(item, f, indent=2)
        f.write("\n")

    print(path)


if __name__ == "__main__":
    main()

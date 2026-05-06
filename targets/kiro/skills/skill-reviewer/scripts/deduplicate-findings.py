#!/usr/bin/env python3
"""Deduplicate findings on exact file:line match.

Reads JSON findings from stdin, deduplicates on file:line, and prints
deduplicated findings plus near-duplicate groups for agent review.

Input format (JSON array):
  [{"title": "...", "file_line": "SKILL.md:56", "description": "...",
    "fix": "...", "severity": "Error", "source": "conventions"}, ...]

Output: JSON with "unique" (deduplicated) and "near_dupes" (groups
sharing file:line where titles differ significantly).
"""
import json
import sys


def main():
    findings = json.load(sys.stdin)
    seen = {}  # file_line -> first finding
    near_dupes = []

    for f in findings:
        key = f.get("file_line", "")
        if key not in seen:
            seen[key] = f
        else:
            near_dupes.append({"kept": seen[key]["title"],
                               "dropped": f["title"],
                               "file_line": key})

    json.dump({"unique": list(seen.values()),
               "near_dupes": near_dupes}, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()

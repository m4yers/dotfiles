#!/usr/bin/env python3
"""List installed skill namespaces, or check a new retro target path.

Default: print one name per line for every top-level directory (real or
symlink) under ~/.kiro/skills/. Exit 1 if ~/.kiro/skills/ does not exist.

--check --area AREA --location LOC --name NAME:
  Resolve where a new skill or steering file would be written:
    skill     ~/.kiro/skills/LOC/NAME/
    steering  ~/.kiro/steering/LOC/NAME.md
  Exit 1 with "error: ..." on stderr if ~/.kiro/{skills,steering}/LOC/ is
  missing, LOC or NAME is malformed, or the target path already exists.
  On success print the target path on stdout.
"""

import argparse
import locale
import re
import sys
from pathlib import Path

KIRO = Path.home() / ".kiro"
SKILLS_DIR = KIRO / "skills"
AREA_ROOTS = {"skill": SKILLS_DIR, "steering": KIRO / "steering"}
# Same character set as skill names (sifu authoring.md AUT-3-2).
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def fail(msg):
    print("error: {}".format(msg), file=sys.stderr)
    sys.exit(1)


def list_namespaces():
    if not SKILLS_DIR.is_dir():
        fail("{} does not exist".format(SKILLS_DIR))
    # is_dir() follows symlinks; hidden entries are skipped and names are
    # collated by locale, both like a shell glob.
    locale.setlocale(locale.LC_COLLATE, "")
    names = sorted((p.name for p in SKILLS_DIR.iterdir()
                    if not p.name.startswith(".") and p.is_dir()),
                   key=locale.strxfrm)
    for name in names:
        print(name)


def check_target(area, location, name):
    parts = location.strip("/").split("/")
    if not location.strip("/") or any(not NAME_RE.match(p) for p in parts):
        fail("bad location {!r}: use slash-separated kebab names".format(location))
    if not NAME_RE.match(name):
        fail("bad name {!r}: use lowercase letters, digits, hyphens".format(name))
    parent = AREA_ROOTS[area].joinpath(*parts)
    if not parent.is_dir():
        fail("{} does not exist".format(parent))
    target = parent / name if area == "skill" else parent / (name + ".md")
    if target.exists() or target.is_symlink():
        fail("{} already exists; refusing to overwrite".format(target))
    print(target)


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--check", action="store_true", help="check a target path")
    p.add_argument("--area", choices=sorted(AREA_ROOTS))
    p.add_argument("--location", help="namespace, e.g. home or aws/util")
    p.add_argument("--name", help="skill or steering file name, no extension")
    args = p.parse_args()

    if not args.check:
        if args.area or args.location or args.name:
            p.error("--area/--location/--name require --check")
        list_namespaces()
        return
    if not (args.area and args.location and args.name):
        p.error("--check requires --area, --location and --name")
    check_target(args.area, args.location, args.name)


if __name__ == "__main__":
    main()

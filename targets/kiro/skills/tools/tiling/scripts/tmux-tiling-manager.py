#!/usr/bin/env python3
"""Tmux tiling manager CLI for kiro-cli skills.

Pane-centric API — no window concept exposed to callers.
All commands operate on panes within the current window.

Uses a custom tmux binary at ~/lib/tmux-3.2a/tmux.

Usage:
    tmux-tiling-manager.py <group> <command> [options]

Groups:
    layout    build, check, reset
    pane      split, write, read, list, kill, resize
    activity  set

Dependencies:
    libtmux >= 0.55.0 (managed via pyproject.toml + uv)
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

import libtmux

TMUX_BIN = str(Path.home() / "tmux")


def server():
    """Create a libtmux Server using the custom tmux binary."""
    return libtmux.Server(tmux_bin=TMUX_BIN)


def find_pane(s, pane_id):
    """Look up a pane by ID. Exits with error if not found."""
    if not pane_id.startswith("%"):
        print(f"invalid pane ID '{pane_id}': must start with %", file=sys.stderr)
        sys.exit(1)
    p = s.panes.get(pane_id=pane_id, default=None)
    if not p:
        print(f"pane {pane_id} not found", file=sys.stderr)
        sys.exit(1)
    return p


def current_pane_id():
    """Return the pane ID of the calling process via TMUX_PANE."""
    pane_id = os.environ.get("TMUX_PANE")
    if not pane_id:
        print("not inside tmux", file=sys.stderr)
        sys.exit(1)
    return pane_id


def resolve_target(args_target):
    """Return args_target if set, otherwise current pane."""
    return args_target or current_pane_id()


def cmd_split(args):
    """Split a pane to create a new one.

    Args:
        -t PANE:  Pane to split (default: current pane).
        -d DIR:   right, left, below, above (default: right).
        -s SIZE:  Percentage or line count (default: 50%).

    Output: new pane ID.
    """
    target = resolve_target(args.target)
    s = server()
    find_pane(s, target)
    flags = {"right": "-h", "left": "-hb", "below": "-v", "above": "-vb"}
    f = flags.get(args.direction)
    if not f:
        print(f"invalid direction: {args.direction}", file=sys.stderr)
        sys.exit(1)
    raw = [TMUX_BIN, "split-window", f,
           "-t", target, "-l", args.size, "-d",
           "-P", "-F", "#{pane_id}"]
    result = subprocess.run(raw, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    print(result.stdout.strip())


def cmd_write(args):
    """Send keystrokes to a pane.

    Args:
        -t PANE:  Target pane ID (required).
        -n:       Suppress trailing Enter.
        KEYS:     Key sequence (positional).
    """
    s = server()
    pane = find_pane(s, args.target)
    pane.send_keys(args.keys, enter=not args.no_enter)


def cmd_read(args):
    """Read visible content of a pane.

    Args:
        -t PANE:   Target pane ID (required).
        -n LINES:  Lines from bottom (default: 15).

    Output: captured lines to stdout.
    """
    s = server()
    pane = find_pane(s, args.target)
    for line in pane.capture_pane()[-args.lines:]:
        print(line)


def cmd_list(args):
    """List panes in the current window.

    Output: one line per pane as '%id: command'.
    """
    s = server()
    pane = find_pane(s, current_pane_id())
    for p in pane.window.panes:
        print(f"{p.pane_id}: {p.pane_current_command}")


def cmd_kill(args):
    """Kill a pane.

    Args:
        -t PANE:  Pane ID to kill (required).
    """
    s = server()
    find_pane(s, args.target).kill()


def cmd_resize(args):
    """Resize a pane.

    Args:
        -t PANE:  Pane to resize (required).
        -d DIR:   up, down, left, right (required).
        -s SIZE:  Amount in lines/columns or percentage
                  (default: 5).
    """
    s = server()
    find_pane(s, args.target)
    direction_flags = {
        "up": "-U", "down": "-D", "left": "-L", "right": "-R",
    }
    f = direction_flags.get(args.direction)
    if not f:
        print(f"invalid direction: {args.direction}", file=sys.stderr)
        sys.exit(1)
    raw = [TMUX_BIN, "resize-pane", "-t", args.target, f, str(args.size)]
    result = subprocess.run(raw, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)


def cmd_set_activity(args):
    """Set the activity label shown in the status bar.

    Renames the current window to reflect what the active
    skill is doing. Skills call this when starting work.

    Args:
        LABEL:  Activity description (positional).
    """
    s = server()
    pane = find_pane(s, current_pane_id())
    pane.window.rename_window(args.label)


def cmd_build(args):
    """Build the standard 3-pane layout.

    If the layout already exists, returns existing pane IDs.
    Otherwise splits the current pane to create EDITOR
    (63% width) and CONSOLE (10% height).

    Layout:
        ┌──────────┬───────────────┐
        │ KIRO 37% │ EDITOR 63%    │
        │ 90%h     │ 100%h         │
        ├──────────┤               │
        │ CONSOLE  │               │
        └──────────┴───────────────┘

    Output: KIRO=%id EDITOR=%id CONSOLE=%id for eval.
    """
    target = current_pane_id()
    s = server()
    kiro = find_pane(s, target)
    panes = kiro.window.panes

    # Check if layout already exists
    if len(panes) == 3:
        kiro_left = int(kiro.pane_left)
        editor = console = None
        for p in panes:
            if p.pane_id == target:
                continue
            if int(p.pane_left) > kiro_left:
                editor = p.pane_id
            else:
                console = p.pane_id
        if editor and console:
            print(f"KIRO={target}")
            print(f"EDITOR={editor}")
            print(f"CONSOLE={console}")
            return

    raw = [TMUX_BIN, "split-window", "-h", "-t", target,
           "-l", "63%", "-d", "-P", "-F", "#{pane_id}"]
    r1 = subprocess.run(raw, capture_output=True, text=True)
    if r1.returncode != 0:
        print(r1.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    editor = r1.stdout.strip()
    raw2 = [TMUX_BIN, "split-window", "-v", "-t", target,
            "-l", "10%", "-d", "-P", "-F", "#{pane_id}"]
    r2 = subprocess.run(raw2, capture_output=True, text=True)
    if r2.returncode != 0:
        print(r2.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    print(f"KIRO={target}")
    print(f"EDITOR={editor}")
    print(f"CONSOLE={r2.stdout.strip()}")


def cmd_check(args):
    """Check if the standard 3-pane layout exists.

    Verifies 3 panes exist and identifies EDITOR and
    CONSOLE relative to the KIRO pane.

    Output: KIRO=%id EDITOR=%id CONSOLE=%id for eval,
    or error message and exit 1.
    """
    target = current_pane_id()
    s = server()
    kiro = find_pane(s, target)
    panes = kiro.window.panes
    if len(panes) != 3:
        print(f"expected 3 panes, found {len(panes)}", file=sys.stderr)
        sys.exit(1)
    kiro_left = int(kiro.pane_left)
    editor = console = None
    for p in panes:
        if p.pane_id == target:
            continue
        if int(p.pane_left) > kiro_left:
            editor = p.pane_id
        else:
            console = p.pane_id
    if not editor or not console:
        print(f"layout incomplete: EDITOR={editor} CONSOLE={console}",
              file=sys.stderr)
        sys.exit(1)
    print(f"KIRO={target}")
    print(f"EDITOR={editor}")
    print(f"CONSOLE={console}")


def cmd_reset(args):
    """Reset layout by killing all panes except the caller.

    Output: KIRO=%id for eval.
    """
    target = current_pane_id()
    s = server()
    kiro = find_pane(s, target)
    for p in kiro.window.panes:
        if p.pane_id != target:
            p.kill()
    print(f"KIRO={target}")


def main():
    p = argparse.ArgumentParser(
        prog="tmux-tiling-manager",
        description="Pane-centric tiling manager for kiro-cli.",
    )
    group = p.add_subparsers(dest="group", required=True)

    # --- layout ---
    layout = group.add_parser("layout", help="Layout management")
    layout_sub = layout.add_subparsers(dest="command", required=True)

    bu = layout_sub.add_parser("build", help="Build standard 3-pane layout")

    ch = layout_sub.add_parser("check", help="Check standard layout exists")

    layout_sub.add_parser("reset", help="Kill all panes except caller")

    # --- pane ---
    pane = group.add_parser("pane", help="Pane operations")
    pane_sub = pane.add_subparsers(dest="command", required=True)

    sp = pane_sub.add_parser("split", help="Split pane, print new ID")
    sp.add_argument("-t", dest="target", default=None,
                    help="pane to split (default: current)")
    sp.add_argument("-d", dest="direction", default="right",
                    help="right|left|below|above")
    sp.add_argument("-s", dest="size", default="50%",
                    help="size (default: 50%%)")

    se = pane_sub.add_parser("write", help="Send keys to a pane")
    se.add_argument("-t", dest="target", required=True,
                    help="target pane ID")
    se.add_argument("-n", dest="no_enter", action="store_true",
                    help="suppress trailing Enter")
    se.add_argument("keys", help="key sequence to send")

    ca = pane_sub.add_parser("read", help="Read pane content")
    ca.add_argument("-t", dest="target", required=True,
                    help="target pane ID")
    ca.add_argument("-n", dest="lines", type=int, default=15,
                    help="lines from bottom (default: 15)")

    pane_sub.add_parser("list", help="List panes in current window")

    ki = pane_sub.add_parser("kill", help="Kill a pane")
    ki.add_argument("-t", dest="target", required=True,
                    help="pane ID to kill")

    rs = pane_sub.add_parser("resize", help="Resize a pane")
    rs.add_argument("-t", dest="target", required=True,
                    help="pane to resize")
    rs.add_argument("-d", dest="direction", required=True,
                    help="up|down|left|right")
    rs.add_argument("-s", dest="size", type=int, default=5,
                    help="amount in lines/columns (default: 5)")

    # --- activity ---
    activity = group.add_parser("activity", help="Activity management")
    activity_sub = activity.add_subparsers(dest="command", required=True)

    sa = activity_sub.add_parser("set", help="Set activity label")
    sa.add_argument("label", help="activity description")

    args = p.parse_args()
    dispatch = {
        ("layout", "build"): cmd_build,
        ("layout", "check"): cmd_check,
        ("layout", "reset"): cmd_reset,
        ("pane", "split"): cmd_split,
        ("pane", "write"): cmd_write,
        ("pane", "read"): cmd_read,
        ("pane", "list"): cmd_list,
        ("pane", "kill"): cmd_kill,
        ("pane", "resize"): cmd_resize,
        ("activity", "set"): cmd_set_activity,
    }
    dispatch[(args.group, args.command)](args)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Editor commands for the EDITOR pane.

Wraps vim — callers don't need to know the implementation.

Usage: editor.py <command> [args]

Commands:
    reset                    Clear all tabs and buffers
    show diff <file> <ref>   Side-by-side diff against ref
    show file <file>         Open file in a new tab
    show tabs                List open tabs and files
"""
import argparse
import sys
import time
from pathlib import Path

# Import tiling manager internals
sys.path.insert(0, str(Path.home() / ".kiro/skills/util/tiling/scripts"))
import importlib
tm = importlib.import_module("tmux-tiling-manager")


def resolve_editor():
    """Get the EDITOR pane ID from layout check."""
    s = tm.server()
    kiro = tm.find_pane(s, tm.current_pane_id())
    panes = kiro.window.panes
    if len(panes) != 3:
        print(f"layout not set up ({len(panes)} panes)", file=sys.stderr)
        sys.exit(1)
    kiro_left = int(kiro.pane_left)
    for p in panes:
        if p.pane_id != kiro.pane_id and int(p.pane_left) > kiro_left:
            return p
    print("EDITOR pane not found", file=sys.stderr)
    sys.exit(1)


def ensure_vim(pane):
    """Start vim in the pane if not already running."""
    if pane.pane_current_command != "vim":
        pane.send_keys("vim -n --cmd 'set shortmess=aoOtTWICF'")
        time.sleep(0.5)


def vcmd(pane, cmd):
    """Send a vim command, ensuring normal mode first."""
    pane.send_keys("Escape", enter=False)
    time.sleep(0.1)
    pane.send_keys(cmd)


def cmd_reset(args):
    """Clear all tabs, splits, and buffers."""
    pane = resolve_editor()
    if pane.pane_current_command == "vim":
        vcmd(pane, ":tabonly")
        time.sleep(0.1)
        vcmd(pane, ":only")
        time.sleep(0.1)
        vcmd(pane, ":enew | only | %bdelete")


def _is_clean_vim(pane):
    """Check if vim has a single empty unnamed buffer."""
    import tempfile
    tmp = tempfile.mktemp(suffix=".txt")
    vcmd(pane, f":redir! > {tmp} | silent tabs | redir END")
    time.sleep(0.2)
    try:
        out = Path(tmp).read_text().strip()
        lines = [l for l in out.splitlines() if l.strip()]
        # Clean vim: one "Tab page 1" line and one "> [No Name]" line
        return (len(lines) == 2
                and "Tab page 1" in lines[0]
                and "[No Name]" in lines[1])
    except FileNotFoundError:
        return False
    finally:
        Path(tmp).unlink(missing_ok=True)


def _open_or_reuse(pane, vim_new_tab_cmd, vim_reuse_cmd, filename):
    """Open in current tab if clean, reuse existing tab, or new tab."""
    if _is_clean_vim(pane):
        vcmd(pane, vim_reuse_cmd)
        return
    # Search all tabs for the file, switch if found
    vim_expr = (
        f":let found=0 | "
        f"for t in range(1,tabpagenr('$')) | "
        f"  for b in tabpagebuflist(t) | "
        f"    if fnamemodify(bufname(b),':p')==fnamemodify('{filename}',':p') | "
        f"      exe 'tabn '.t | let found=1 | break | "
        f"    endif | "
        f"  endfor | "
        f"  if found | break | endif | "
        f"endfor | "
        f"if found | {vim_reuse_cmd[1:]} | "
        f"else | {vim_new_tab_cmd[1:]} | endif"
    )
    vcmd(pane, vim_expr)


def cmd_show_diff(args):
    """Open file with side-by-side diff against ref.

    Reuses existing tab if the file is already open.
    Uses current tab if vim is clean (no files open).
    """
    pane = resolve_editor()
    ensure_vim(pane)
    new_cmd = f":tabnew {args.file} | Gvdiffsplit {args.ref}"
    reuse_cmd = f":e {args.file} | only | Gvdiffsplit {args.ref}"
    _open_or_reuse(pane, new_cmd, reuse_cmd, args.file)


def cmd_show_file(args):
    """Open file in a tab.

    Reuses existing tab if open. Uses current tab if vim
    is clean (no files open).
    """
    pane = resolve_editor()
    ensure_vim(pane)
    new_cmd = f":tabnew {args.file}"
    reuse_cmd = f":e {args.file} | only"
    _open_or_reuse(pane, new_cmd, reuse_cmd, args.file)


def cmd_show_only(args):
    """Reset editor and show a single file."""
    cmd_reset(args)
    time.sleep(0.1)
    cmd_show_file(args)


def cmd_list_tabs(args):
    """List all tabs with their splits and open files.

    Returns JSON: list of tabs, each with a list of panes
    (files), marking the active pane.
    """
    import json
    import tempfile
    pane = resolve_editor()
    if pane.pane_current_command != "vim":
        print("editor not running", file=sys.stderr)
        sys.exit(1)
    tmp = tempfile.mktemp(suffix=".txt")
    vcmd(pane, f":redir! > {tmp} | silent tabs | redir END")
    time.sleep(0.3)
    try:
        raw = Path(tmp).read_text().strip()
    except FileNotFoundError:
        print("could not read tabs output", file=sys.stderr)
        sys.exit(1)
    finally:
        Path(tmp).unlink(missing_ok=True)

    tabs = []
    current_tab = None
    for line in raw.splitlines():
        line = line.rstrip()
        if line.startswith("Tab page"):
            current_tab = {"tab": int(line.split()[-1]), "panes": []}
            tabs.append(current_tab)
        elif current_tab is not None and line.strip():
            active = line.lstrip().startswith(">")
            name = line.lstrip("> \t")
            current_tab["panes"].append({
                "file": name,
                "active": active,
            })
    print(json.dumps(tabs, indent=2))


def main():
    p = argparse.ArgumentParser(prog="editor")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("reset", help="Clear all tabs and buffers")

    show = sub.add_parser("show", help="Show content")
    show_sub = show.add_subparsers(dest="show_command", required=True)

    diff = show_sub.add_parser("diff", help="Side-by-side diff")
    diff.add_argument("file", help="file path")
    diff.add_argument("ref", help="git ref (HEAD, HEAD~1, rc, etc.)")

    file = show_sub.add_parser("file", help="Open file in new tab")
    file.add_argument("file", help="file path")

    only = show_sub.add_parser("only", help="Reset and show single file")
    only.add_argument("file", help="file path")

    # --- list ---
    lst = sub.add_parser("list", help="List editor state")
    list_sub = lst.add_subparsers(dest="list_command", required=True)
    list_sub.add_parser("tabs", help="List open tabs and files")

    args = p.parse_args()
    {
        "reset": cmd_reset,
        "show": lambda a: {
            "diff": cmd_show_diff,
            "file": cmd_show_file,
            "only": cmd_show_only,
        }[a.show_command](a),
        "list": lambda a: {
            "tabs": cmd_list_tabs,
        }[a.list_command](a),
    }[args.command](args)


if __name__ == "__main__":
    main()

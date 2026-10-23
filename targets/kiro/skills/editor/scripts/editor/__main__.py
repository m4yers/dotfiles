#!/usr/bin/env python3
"""Editor commands for the EDITOR pane.

Wraps vim for file views and tabs. Diffs are shown via
`delta` — `cmd_show_diff` runs `git diff` in the pane's
shell and delta pages the output; callers don't need to
know either implementation.

Usage: run-editor.sh <command> [args]

Commands:
    reset                    Clear all tabs and buffers
    show diff <file> <ref>   Side-by-side diff via delta
    show file <file>         Open file in a new tab
    show tabs                List open tabs and files
"""
import argparse
import os
import sys
import time
from pathlib import Path

import libtmux


# Custom tmux binary — matches the tiling skill which
# drives the same tmux server.
TMUX_BIN = "tmux"


# Pager processes that the EDITOR pane may host instead
# of vim (notably after `show diff`, which leaves delta
# running). `ensure_vim` and `cmd_reset` dismiss them
# with `q` before driving vim. tmux reports the pane's
# foreground process as `git` while git is paging through
# delta → less, so `git` must be treated as a pager too.
PAGER_COMMANDS = {"git", "less", "delta"}


def _server():
    """Create a libtmux Server using the custom tmux binary."""
    return libtmux.Server(tmux_bin=TMUX_BIN)


def _current_pane_id():
    """Return the pane ID of the calling process via TMUX_PANE."""
    pane_id = os.environ.get("TMUX_PANE")
    if not pane_id:
        print("not inside tmux", file=sys.stderr)
        sys.exit(1)
    return pane_id


def _find_pane(s, pane_id):
    """Look up a pane by ID. Exits with error if not found."""
    p = s.panes.get(pane_id=pane_id, default=None)
    if not p:
        print(f"pane {pane_id} not found", file=sys.stderr)
        sys.exit(1)
    return p


def dismiss_pager(pane):
    """Send `q` to exit a pager (less/delta) in the pane.

    No-op if the pane is not currently running a pager.
    Gives the pager a brief moment to exit so a following
    check of `pane_current_command` sees the shell.
    """
    if pane.pane_current_command in PAGER_COMMANDS:
        pane.send_keys("q", enter=False)
        time.sleep(0.3)  # delta/less needs ~250ms to tear down


def resolve_editor():
    """Get the EDITOR pane ID from layout check."""
    s = _server()
    kiro = _find_pane(s, _current_pane_id())
    panes = kiro.window.panes
    if len(panes) != 2:
        print(f"layout not set up ({len(panes)} panes)", file=sys.stderr)
        sys.exit(1)
    kiro_left = int(kiro.pane_left)
    for p in panes:
        if p.pane_id != kiro.pane_id and int(p.pane_left) < kiro_left:
            return p
    print("EDITOR pane not found", file=sys.stderr)
    sys.exit(1)


def ensure_vim(pane):
    """Start vim in the pane if not already running.

    Dismisses any running delta/less pager first so the
    pane is back at its shell before vim is launched.
    """
    dismiss_pager(pane)
    if pane.pane_current_command != "vim":
        pane.send_keys("vim -n --cmd 'set shortmess=aoOtTWICF'")
        time.sleep(0.5)  # vim startup + initial redraw


def vcmd(pane, cmd, silent=True):
    """Send a vim command, ensuring normal mode first.

    Commands are wrapped with :silent! by default so vim
    never blocks on 'Press ENTER' prompts. Pass silent=False
    for commands whose output is needed (e.g. :redir).
    """
    pane.send_keys("Escape", enter=False)
    time.sleep(0.1)  # Escape → normal mode settle
    if silent and not cmd.lstrip(":").startswith("silent"):
        cmd = f":silent! {cmd.lstrip(':')}"
    pane.send_keys(cmd)


def cmd_reset(args):
    """Clear all tabs, splits, and buffers.

    Also dismisses any delta/less pager left over from a
    previous `show diff` so the pane returns to a clean
    state regardless of what was running in it.
    """
    pane = resolve_editor()
    dismiss_pager(pane)
    if pane.pane_current_command == "vim":
        vcmd(pane, ":tabonly")
        time.sleep(0.1)  # let :tabonly complete before :only
        vcmd(pane, ":only")
        time.sleep(0.1)  # let :only complete before buffer wipe
        vcmd(pane, ":enew | only | %bdelete")


def _is_clean_vim(pane):
    """Check if vim has a single empty unnamed buffer."""
    import tempfile
    tmp = tempfile.mktemp(suffix=".txt")
    vcmd(pane, f":redir! > {tmp} | silent tabs | redir END", silent=False)
    time.sleep(0.2)  # :redir flush to tempfile
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


def _vim_str_escape(s):
    """Escape a string for use inside vim single-quoted literals.

    Vim single-quoted strings escape ' by doubling: 'Claude''s'.
    """
    return s.replace("'", "''")


def _open_or_reuse(pane, vim_new_tab_cmd, vim_reuse_cmd, filename):
    """Open in current tab if clean, reuse existing tab, or new tab."""
    if _is_clean_vim(pane):
        vcmd(pane, vim_reuse_cmd)
        return
    # Search all tabs for the file, switch if found
    fn_esc = _vim_str_escape(filename)
    vim_expr = (
        f":let found=0 | "
        f"for t in range(1,tabpagenr('$')) | "
        f"  for b in tabpagebuflist(t) | "
        f"    if fnamemodify(bufname(b),':p')==fnamemodify('{fn_esc}',':p') | "
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
    """Show a side-by-side diff of a file against a ref.

    Leaves vim (if running) and runs
    `git -C <repo> diff <ref> -- <file>` in the pane's
    shell. Delta pages the output with syntax
    highlighting and side-by-side layout (configured via
    the user's gitconfig). The pane is left in the
    delta/less pager; navigate with `n`/`N` and quit
    with `q`. The next vim-driven command relaunches vim
    via `ensure_vim`.
    """
    import shlex
    import subprocess
    pane = resolve_editor()
    # If a previous diff is still on screen, dismiss it
    # before touching vim so pane state is well-defined.
    dismiss_pager(pane)
    # Delta runs in the pane's shell, so vim must step
    # aside. :qa! discards any open tabs.
    if pane.pane_current_command == "vim":
        vcmd(pane, ":qa!")
        time.sleep(0.3)  # vim :qa! → shell prompt
    # Resolve symlinks (e.g. ~/.kiro/skills → dotfiles) so
    # the pathspec is inside the repo git reports; a
    # directory pathspec diffs every file under it.
    target = Path(args.file).resolve()
    try:
        repo = subprocess.check_output(
            ["git", "-C", str(target.parent),
             "rev-parse", "--show-toplevel"],
            text=True).strip()
    except subprocess.CalledProcessError:
        print("not in a git repo", file=sys.stderr)
        sys.exit(1)
    pane.send_keys(
        f"git -C {shlex.quote(repo)} diff "
        f"{shlex.quote(args.ref)} -- {shlex.quote(str(target))}"
    )


def cmd_show_file(args):
    """Open file in a tab.

    Reuses existing tab if open. Uses current tab if vim
    is clean (no files open).
    """
    pane = resolve_editor()
    ensure_vim(pane)
    fn_esc = _vim_str_escape(args.file)
    new_cmd = f":execute 'tabnew ' . fnameescape('{fn_esc}')"
    reuse_cmd = (
        f":execute 'edit ' . fnameescape('{fn_esc}') | only"
    )
    _open_or_reuse(pane, new_cmd, reuse_cmd, args.file)


def cmd_show_only(args):
    """Reset editor and show a single file."""
    cmd_reset(args)
    time.sleep(0.1)  # let %bdelete settle before relaunching vim
    cmd_show_file(args)


def cmd_list_tabs(args):
    """List all tabs with their splits and open files.

    Returns JSON: list of tabs, each with a list of panes
    (files), marking the active pane.
    """
    import json
    import tempfile
    pane = resolve_editor()
    ensure_vim(pane)
    tmp = tempfile.mktemp(suffix=".txt")
    vcmd(pane, f":redir! > {tmp} | silent tabs | redir END", silent=False)
    time.sleep(0.3)  # :redir flush to tempfile
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

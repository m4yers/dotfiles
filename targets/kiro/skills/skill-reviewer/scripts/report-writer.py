#!/usr/bin/env python3
"""
report-writer.py — Build skill review reports with enforced structure.

Commands:
  create <path> <name> <category> <type>
    Create a new report file with header and empty sections.

  error <path> <title> <location> <description> <fix>
  warning <path> <title> <location> <description> <fix>
  info <path> <title> <location> <description> <fix>
    Append a finding to the appropriate section. Numbers are
    sequential: errors first, then warnings, then info.

  format <path>
    Wrap prose lines at 80 chars. Preserves markdown structure
    (headings, numbered items, blockquotes, metadata lines).

  strikeout <path> <finding_number>
    Strike out a finding (wrap lines in ~~) after applying it.

  skip <path> <finding_number>
    Deprecated alias for `decline`. Prefer `decline --reason`.

  decline <path> <finding_number> --reason <text>
    Mark a finding as declined by the user (append ⏩ tag).
    Only use after the user explicitly rejects the finding.
    Findings the user did not mention remain open — never
    mark them declined.
"""
import json
import re
import sys
import textwrap

SECTIONS = ["Errors", "Warnings", "Info"]
SECTION_FOR_CMD = {"error": "Errors", "warning": "Warnings", "info": "Info"}

HEADER = """\
# Skill Review: {name}

- **Path:** `~/.kiro/skills/{category}/{name}/`
- **Type:** {type}

## Errors

None.

## Warnings

None.

## Info

None.
"""

# Matches "N. **" at start of line — a numbered finding.
FINDING_RE = re.compile(r"^(\d+)\. \*\*", re.MULTILINE)


def _renumber(text):
    """Renumber all findings sequentially across sections."""
    n = 0
    def _repl(m):
        nonlocal n
        n += 1
        return f"{n}. **"
    return FINDING_RE.sub(_repl, text)


def _get_section_range(text, section):
    """Return (start_of_content, end_of_content) for a section."""
    heading = f"## {section}\n"
    idx = text.find(heading)
    if idx == -1:
        return None
    content_start = idx + len(heading)
    # Find next ## heading
    rest = text[content_start:]
    m = re.search(r"^## ", rest, re.MULTILINE)
    content_end = content_start + m.start() if m else len(text)
    return content_start, content_end


def cmd_create(args):
    path, name, category, typ = args
    with open(path, "w") as f:
        f.write(HEADER.format(name=name, category=category, type=typ))
    print(json.dumps({"status": "created", "path": path}))


def cmd_finding(severity, args):
    path, title, location, description, fix = args
    section = SECTION_FOR_CMD[severity]

    with open(path) as f:
        text = f.read()

    rng = _get_section_range(text, section)
    if rng is None:
        print(json.dumps({"status": "error",
                          "message": f"Section {section} not found"}))
        sys.exit(1)

    start, end = rng
    content = text[start:end]

    # Entry with placeholder number (renumbered below).
    entry = (
        f'0. **{title}** — `{location}`\n'
        f'   {description}\n'
        f'   > {fix}\n'
    )

    # Replace "None." or append after existing findings.
    if re.match(r"\nNone\.\n", content):
        content = "\n" + entry + "\n"
    else:
        content = content.rstrip("\n") + "\n\n" + entry + "\n"

    text = text[:start] + content + text[end:]
    text = _renumber(text)

    with open(path, "w") as f:
        f.write(text)

    # Count to report which number this finding got.
    n = len(FINDING_RE.findall(text))
    print(json.dumps({"status": "ok", "finding": n, "section": section}))


# Matches a full finding block: number line + indented body.
FINDING_BLOCK_RE = re.compile(
    r"^(\d+)\. (\*\*.*?)(?=\n\d+\. \*\*|\n## |\Z)",
    re.MULTILINE | re.DOTALL,
)


def _mark_finding(path, number, marker, reason=None):
    """Apply marker (checkmark or decline) to finding N."""
    with open(path) as f:
        text = f.read()

    found = False
    for m in FINDING_BLOCK_RE.finditer(text):
        if int(m.group(1)) == number:
            old = m.group(0)
            # Already marked — skip.
            first_line = old.split("\n")[0]
            if "✅" in first_line or "⏩" in first_line:
                print(json.dumps({"status": "ok", "already_marked": True}))
                return
            # Insert marker after the number prefix.
            if marker == "decline":
                suffix = f" (declined: {reason})" if reason else ""
                new = re.sub(
                    r"^(\d+\. )(.*)$",
                    lambda mo: f"{mo.group(1)}⏩ {mo.group(2)}{suffix}",
                    old, count=1, flags=re.MULTILINE)
            else:
                new = re.sub(
                    r"^(\d+\. )",
                    r"\g<1>✅ ",
                    old, count=1)
            text = text.replace(old, new)
            found = True
            break

    if not found:
        print(json.dumps({"status": "error",
                          "message": f"Finding {number} not found"}))
        sys.exit(1)

    with open(path, "w") as f:
        f.write(text)
    print(json.dumps({"status": "ok", "finding": number,
                       "marker": marker}))


def cmd_strikeout(args):
    path, number = args
    _mark_finding(path, int(number), "strikeout")


def cmd_decline(args):
    # args: [path, number, "--reason", reason]  OR  [path, number]
    if len(args) == 4 and args[2] == "--reason":
        path, number, _, reason = args
    elif len(args) == 2:
        path, number = args
        reason = None
    else:
        print("Usage: decline <path> <finding_number> --reason <text>",
              file=sys.stderr)
        sys.exit(1)
    if reason is None:
        print("ERROR: decline requires --reason <text>. Use this only "
              "when the user explicitly rejected the finding.",
              file=sys.stderr)
        sys.exit(1)
    _mark_finding(path, int(number), "decline", reason)


def cmd_format(args):
    """Wrap report prose at 80 chars preserving structure."""
    (path,) = args
    with open(path) as f:
        lines = f.readlines()

    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.rstrip("\n")

        # Pass through: blank, headings, metadata, None.
        if (not stripped or stripped.startswith("#")
                or stripped.startswith("- **") or stripped == "None."):
            out.append(line)
            i += 1
            continue

        # Numbered finding title: "N. **...**" — pass through.
        if FINDING_RE.match(stripped):
            out.append(line)
            i += 1
            continue

        # Blockquote description line ("> ...") — collect
        # continuation lines and wrap with "> " prefix.
        if stripped.startswith("   > "):
            text = stripped[5:]  # strip "   > "
            i += 1
            while i < len(lines):
                nxt = lines[i].rstrip("\n")
                if nxt.startswith("   > "):
                    text += " " + nxt[5:]
                    i += 1
                elif nxt.startswith("     ") and nxt.strip():
                    # Continuation of blockquote wrapped by
                    # a previous format run.
                    text += " " + nxt.strip()
                    i += 1
                else:
                    break
            wrapped = textwrap.fill(
                text, width=75,  # 80 - len("   > ")
                initial_indent="   > ",
                subsequent_indent="   > ")
            out.append(wrapped + "\n")
            continue

        # Indented description line ("   text") — collect
        # continuation and wrap with 3-space indent.
        if stripped.startswith("   ") and not stripped.startswith("    "):
            text = stripped.strip()
            i += 1
            while i < len(lines):
                nxt = lines[i].rstrip("\n")
                if (nxt.startswith("   ")
                        and not nxt.startswith("   > ")
                        and not nxt.startswith("   ~~")
                        and not FINDING_RE.match(nxt)
                        and nxt.strip()):
                    text += " " + nxt.strip()
                    i += 1
                else:
                    break
            wrapped = textwrap.fill(
                text, width=80,
                initial_indent="   ",
                subsequent_indent="   ")
            out.append(wrapped + "\n")
            continue

        # Anything else — pass through.
        out.append(line)
        i += 1

    with open(path, "w") as f:
        f.writelines(out)
    print(json.dumps({"status": "ok", "path": path}))


def main():
    if len(sys.argv) < 2:
        print("Usage: report-writer.py <command> <args...>",
              file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    if cmd == "create":
        if len(rest) != 4:
            print("Usage: create <path> <name> <category> <type>",
                  file=sys.stderr)
            sys.exit(1)
        cmd_create(rest)
    elif cmd == "format":
        if len(rest) != 1:
            print("Usage: format <path>", file=sys.stderr)
            sys.exit(1)
        cmd_format(rest)
    elif cmd in SECTION_FOR_CMD:
        if len(rest) != 5:
            print(f"Usage: {cmd} <path> <title> <location> "
                  "<description> <fix>", file=sys.stderr)
            sys.exit(1)
        cmd_finding(cmd, rest)
    elif cmd == "strikeout":
        if len(rest) != 2:
            print("Usage: strikeout <path> <finding_number>",
                  file=sys.stderr)
            sys.exit(1)
        cmd_strikeout(rest)
    elif cmd == "decline":
        cmd_decline(rest)
    elif cmd == "skip":
        print("WARNING: 'skip' is deprecated — use 'decline "
              "<path> <n> --reason <text>'. Only mark findings "
              "the user explicitly rejected.", file=sys.stderr)
        if len(rest) != 2:
            print("Usage: skip <path> <finding_number>",
                  file=sys.stderr)
            sys.exit(1)
        _mark_finding(rest[0], int(rest[1]), "decline",
                      "no reason (legacy skip)")
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

# Tee External Output

When invoking any external tool (build, test,
script, long-running command), redirect both
stdout and stderr to a temp file so the user
can `tail -f` and follow progress.

## Pattern

```bash
TMP=$(mktemp); <command> >"$TMP" 2>&1; cat "$TMP"
```

Or with live streaming:

```bash
<command> 2>&1 | tee /tmp/<name>.log
```

## Rules

- Always combine stderr into stdout (`2>&1`).
- Use `mktemp` or a stable `/tmp/<name>.log` path.
- Print or reference the temp file path in your
  reply so the user knows where to look.

## Exceptions

- Trivial, instant commands (`ls`, `cat`, `pwd`).
- Commands whose output is already captured by a
  dedicated tool wrapper.

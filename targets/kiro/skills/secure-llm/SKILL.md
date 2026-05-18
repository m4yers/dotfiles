---
name: secure-llm
type: interface
description: Shared utilities for working with untrusted text in LLM pipelines. Provides a heuristic security scanner (regex catalog for prompt-injection / role-override / delimiter-spoof / unicode-trick / exfiltration / resource-attack patterns) and a security-frame Jinja preamble that instructs LLMs to treat source content as data, not commands. Other skills compose these into their fetch / extract / classify pipelines.
---

# secure-llm

Two complementary defences against untrusted-text attacks in
LLM-driven pipelines:

1. **Mechanical** — `security_scan` package + `security-scan.sh`
   wrapper. Runs a regex catalogue over a file or string; emits a
   YAML report with `verdict: PASS | FAIL`, per-check status, and
   capped finding excerpts.
2. **Instructional** — `templates/security-frame.md.j2`. A Jinja
   include other skills prepend to extractor / judge prompts so
   the LLM is reminded the source is untrusted before it reads.

Together they give an ingestion pipeline a defence in depth: the
scanner catches obvious injection patterns before the LLM sees
the text; the frame instructs the LLM to ignore any patterns the
scanner missed.

## Usage

### Library (Python)

    from security_scan import scan_text, scan_file

    result = scan_text("Some untrusted text…")
    if result["verdict"] == "FAIL":
        for f in result["findings"]:
            ...

    result = scan_file(Path("/path/to/source.md"))

### Standalone CLI

    $SKILLS/home/secure-llm/scripts/security-scan.sh <path>

Emits YAML on stdout. Exit 0 on `PASS`, 1 on `FAIL`.

### Security-frame include in agent prompts

Other skills' Jinja templates use:

    {% include 'security-frame.md.j2' %}

Pass `$SKILLS/home/secure-llm/templates` as an additional
`--include-dir` to `$SKILLS/home/template/scripts/render.sh` so
the include resolves.

## Result shape

`scan_text` and `scan_file` return:

| Field             | Meaning                                              |
|-------------------|------------------------------------------------------|
| `verdict`         | `"PASS"` if all checks pass, `"FAIL"` otherwise.     |
| `ok`              | `True` iff verdict is PASS.                          |
| `checks`          | Every check that ran, with `status` + `matches`.     |
| `findings`        | Capped per-pattern excerpts for the failed checks.   |
| `summary`         | Match counts by category.                            |
| `scanned`         | Input path (file form only).                         |
| `file_size`       | Input bytes (file form only).                        |

## Pattern coverage

- **prompt_injection** — "ignore previous", "you are now", "new
  instructions" patterns.
- **role_override** — `system:` / `assistant:` / `[INST]` / xml
  persona tags.
- **delimiter_spoof** — `<|im_start|>`-style chat delimiters,
  spoofed BEGIN/END UNTRUSTED frames.
- **unicode_trick** — zero-width / RTL-override / direction
  isolate / U+E0000–E007F tag characters.
- **exfiltration** — markdown image with query-string URL,
  shell `curl|wget|fetch http(s)://`.
- **steganography** — long unbroken base64-like blobs (>500
  chars).
- **resource_attack** — file size > 5 MB, line length > 10 000
  chars.

Add patterns by editing `scripts/security_scan/__init__.py`
`_PATTERNS` list. Each entry is
`(name, category, severity, compiled_regex, description)`.

"""security_scan — heuristic security scanner for untrusted text.

Detects prompt-injection attempts, role-override patterns,
delimiter spoofing, unicode tricks, exfiltration markers, and
resource attacks in arbitrary text. Pure-Python regex catalog plus
two file-size / line-length checks.

## Library use

    from security_scan import scan_text, scan_file

    result = scan_text("Some untrusted text...")
    if result["verdict"] == "FAIL":
        for finding in result["findings"]:
            ...

    result = scan_file(Path("/path/to/source.md"))

## Standalone CLI

    security-scan /path/to/source.md
    # emits YAML on stdout; exit 0 on PASS, 1 on FAIL.

The result dict is the canonical contract:

- ``verdict``      — ``"PASS"`` or ``"FAIL"``.
- ``ok``           — ``True`` iff verdict is PASS.
- ``checks``       — every check that ran, with ``status``
                      (PASS/FAIL) + ``matches`` count.
- ``findings``     — capped per-check excerpts for the failed
                      ones.
- ``summary``      — match counts by category.
- ``scanned``      — input path (file form only).
- ``file_size``    — input size in bytes (file form only).
"""
from __future__ import annotations

import re
from pathlib import Path


# ── pattern catalog ─────────────────────────────────────
#
# Each entry: (name, category, severity, compiled regex,
# description). The ``name`` is a stable identifier callers can
# pattern-match on. Severity is informational — any match is FAIL.

_PATTERNS: list[tuple[str, str, str, "re.Pattern[str]", str]] = [
    # Direct injection
    ("prompt_injection.ignore_previous",
     "prompt_injection", "high",
     re.compile(
         r"\b(ignore|disregard)\b[^.\n]{0,40}\b(previous|above|all|prior)"
         r"\b[^.\n]{0,40}\b(instructions?|prompts?|rules?|directives?)\b",
         re.IGNORECASE),
     "explicit 'ignore previous instructions' style attack"),
    ("prompt_injection.role_override_text",
     "prompt_injection", "high",
     re.compile(r"\byou\s+are\s+now\s+(an?|the)\s+\w+", re.IGNORECASE),
     "role override ('you are now ...')"),
    ("prompt_injection.new_instructions",
     "prompt_injection", "high",
     re.compile(r"\bnew\s+(instructions?|task|directives?)[\s:]*",
                 re.IGNORECASE),
     "claimed new instructions"),

    # Role override / system markers
    ("role_override.line_prefix",
     "role_override", "high",
     re.compile(r"^\s*(system|assistant|user)\s*:",
                 re.IGNORECASE | re.MULTILINE),
     "fake role prefix at line start"),
    ("role_override.xml_tag",
     "role_override", "medium",
     re.compile(r"</?\s*(system|prompt|instruction|persona)\s*>",
                 re.IGNORECASE),
     "fake xml-style role tag"),
    ("role_override.inst_marker",
     "role_override", "medium",
     re.compile(r"\[\s*(INST|/INST|SYSTEM|/SYSTEM)\s*\]"),
     "[INST] / [SYSTEM] markers"),

    # Delimiter spoofing
    ("delimiter_spoof.chat_delimiter",
     "delimiter_spoof", "medium",
     re.compile(
         r"<\|\s*(im_start|im_end|endoftext|system|user|assistant)\s*\|>",
         re.IGNORECASE),
     "OpenAI/Anthropic-style delimiter"),
    ("delimiter_spoof.security_frame",
     "delimiter_spoof", "medium",
     re.compile(r"---\s*(BEGIN|END)\s+UNTRUSTED\b", re.IGNORECASE),
     "tries to spoof a security-frame delimiter"),

    # Unicode tricks
    ("unicode_trick.invisible_chars",
     "unicode_trick", "medium",
     re.compile(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]"),
     "zero-width / RTL-override / direction-isolate character"),
    ("unicode_trick.tag_chars",
     "unicode_trick", "medium",
     re.compile(r"[\U000E0000-\U000E007F]"),
     "tag / private-use character (U+E0000–U+E007F)"),

    # Exfiltration markers
    ("exfiltration.image_query",
     "exfiltration", "medium",
     re.compile(r"!\[[^\]]*\]\([^)]*\?[a-z]+="),
     "markdown image with query-string URL (potential exfil)"),
    ("exfiltration.shell_fetch",
     "exfiltration", "medium",
     re.compile(r"\b(curl|wget|fetch)\s+https?://", re.IGNORECASE),
     "command-line fetch instruction"),

    # Excessively long base64-like blobs (potential steganography)
    ("steganography.long_base64",
     "steganography", "low",
     re.compile(r"[A-Za-z0-9+/=]{500,}"),
     "very long base64-like blob (>500 chars unbroken)"),
]


# ── thresholds ──────────────────────────────────────────

# Per-line cap — defends against single megaline payloads that
# blow up downstream LLM context budgets.
MAX_LINE_LENGTH = 10_000

# Whole-file cap. 5 MB ≈ a long book PDF text-extracted; anything
# bigger is almost certainly an attack or malformed input.
MAX_FILE_SIZE = 5 * 1024 * 1024

# Per-pattern cap on findings emitted. Findings beyond this fold
# into a single "N additional truncated" entry per pattern so a
# pathological match count cannot inflate the output indefinitely.
PER_PATTERN_CAP = 5


# ── public API ──────────────────────────────────────────


def scan_text(text: str, *, file_size: int | None = None) -> dict:
    """Scan an in-memory string. Pure function; no I/O.

    ``file_size`` is informational and only used for the
    resource-attack file-size check. Pass ``len(text.encode())`` if
    you want that check to run; pass ``None`` to skip it.
    """
    findings: list[dict] = []
    checks:   list[dict] = []

    if file_size is not None:
        size_ok = file_size <= MAX_FILE_SIZE
        _record_check(
            checks, name="resource.file_size",
            category="resource_attack", severity="high",
            description=f"file size <= {MAX_FILE_SIZE} bytes",
            matches=0 if size_ok else 1,
            notes=f"actual: {file_size} bytes",
        )
        if not size_ok:
            findings.append({
                "category":    "resource_attack",
                "severity":    "high",
                "description":
                    f"file size {file_size} exceeds limit "
                    f"{MAX_FILE_SIZE}",
            })

    long_lines = [
        (i, len(line))
        for i, line in enumerate(text.splitlines(), 1)
        if len(line) > MAX_LINE_LENGTH
    ]
    _record_check(
        checks, name="resource.line_length",
        category="resource_attack", severity="high",
        description=f"every line <= {MAX_LINE_LENGTH} chars",
        matches=len(long_lines),
        notes=f"longest line: "
              f"{max((n for _, n in long_lines), default=0)}",
    )
    for line_no, line_len in long_lines:
        findings.append({
            "category":    "resource_attack",
            "severity":    "high",
            "line":        line_no,
            "description":
                f"line length {line_len} exceeds {MAX_LINE_LENGTH}",
        })

    for name, category, severity, regex, description in _PATTERNS:
        all_matches = list(regex.finditer(text))
        _record_check(
            checks, name=name,
            category=category, severity=severity,
            description=description,
            matches=len(all_matches),
        )
        for m in all_matches[:PER_PATTERN_CAP]:
            line_no = text.count("\n", 0, m.start()) + 1
            excerpt = m.group(0)
            if len(excerpt) > 120:
                excerpt = excerpt[:120] + "..."
            findings.append({
                "category":    category,
                "severity":    severity,
                "description": description,
                "name":        name,
                "line":        line_no,
                "excerpt":     excerpt,
            })
        truncated = len(all_matches) - PER_PATTERN_CAP
        if truncated > 0:
            findings.append({
                "category":    category,
                "severity":    severity,
                "name":        name,
                "description":
                    f"{description} — {truncated} additional "
                    f"match(es) truncated",
            })

    summary: dict[str, int] = {}
    for f in findings:
        summary[f["category"]] = summary.get(f["category"], 0) + 1

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {
        "verdict":       "FAIL" if findings else "PASS",
        "ok":            len(findings) == 0,
        "checks":        checks,
        "checks_passed": pass_count,
        "checks_failed": fail_count,
        "findings":      findings,
        "summary":       summary,
    }


def scan_file(path: Path) -> dict:
    """Scan a file. File-existence + size are checked alongside
    the in-memory pattern catalog.

    Returns the same result shape as ``scan_text`` plus
    ``scanned`` (the input path) and ``file_size``.
    """
    p = Path(path)
    if not p.exists():
        return {
            "verdict": "FAIL",
            "ok":      False,
            "checks": [{
                "name":        "input.exists",
                "category":    "missing_file",
                "severity":    "high",
                "description": "input file present and readable",
                "status":      "FAIL",
                "matches":     1,
                "notes":       f"file not found: {p}",
            }],
            "findings": [{
                "category":    "missing_file",
                "severity":    "high",
                "description": f"file not found: {p}",
            }],
            "summary": {"missing_file": 1},
            "scanned":   str(p),
            "file_size": 0,
        }

    file_size = p.stat().st_size
    text = p.read_text(encoding="utf-8", errors="replace")

    result = scan_text(text, file_size=file_size)

    # Prepend the input.exists check at the top of ``checks`` so
    # the failure story ("file missing") would always lead — kept
    # consistent with the failure path above.
    result["checks"].insert(0, {
        "name":        "input.exists",
        "category":    "missing_file",
        "severity":    "high",
        "description": "input file present and readable",
        "status":      "PASS",
        "matches":     0,
    })
    result["checks_passed"] += 1

    result["scanned"]   = str(p)
    result["file_size"] = file_size
    return result


def _record_check(checks: list[dict], *, name: str, category: str,
                    severity: str, description: str, matches: int,
                    notes: str | None = None) -> None:
    entry = {
        "name":        name,
        "category":    category,
        "severity":    severity,
        "description": description,
        "status":      "FAIL" if matches > 0 else "PASS",
        "matches":     matches,
    }
    if notes:
        entry["notes"] = notes
    checks.append(entry)


__all__ = [
    "MAX_FILE_SIZE",
    "MAX_LINE_LENGTH",
    "PER_PATTERN_CAP",
    "scan_file",
    "scan_text",
]

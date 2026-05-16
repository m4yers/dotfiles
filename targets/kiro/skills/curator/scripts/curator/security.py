"""Heuristic security scan — runs between convert and classify.

Pure-Python regex pass over the converted source text. Detects
prompt injection, role override attempts, delimiter spoofing,
unicode tricks, exfiltration markers, and resource attacks.

Output:

* ``verdict`` — PASS if every check passes, FAIL otherwise.
* ``checks`` — every check that ran, with PASS/FAIL outcome and
  match count.
* ``findings`` — capped per-check excerpts for the failed ones.
* ``summary`` — match counts by category.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer

from curator.utils import emit, fail


# ── pattern catalog ─────────────────────────────────────────────

# Each entry: (name, category, severity, compiled regex, description).
# The ``name`` is a stable identifier for the check. Severity is
# informational — any match is FAIL.
_PATTERNS: list[tuple[str, str, str, re.Pattern, str]] = [
    # Direct injection
    ("prompt_injection.ignore_previous",
     "prompt_injection", "high",
     re.compile(r"\b(ignore|disregard)\b[^.\n]{0,40}\b(previous|above|all|prior)\b[^.\n]{0,40}\b(instructions?|prompts?|rules?|directives?)\b",
                 re.IGNORECASE),
     "explicit 'ignore previous instructions' style attack"),
    ("prompt_injection.role_override_text",
     "prompt_injection", "high",
     re.compile(r"\byou\s+are\s+now\s+(an?|the)\s+\w+", re.IGNORECASE),
     "role override ('you are now ...')"),
    ("prompt_injection.new_instructions",
     "prompt_injection", "high",
     re.compile(r"\bnew\s+(instructions?|task|directives?)[\s:]*", re.IGNORECASE),
     "claimed new instructions"),

    # Role override / system markers
    ("role_override.line_prefix",
     "role_override", "high",
     re.compile(r"^\s*(system|assistant|user)\s*:", re.IGNORECASE | re.MULTILINE),
     "fake role prefix at line start"),
    ("role_override.xml_tag",
     "role_override", "medium",
     re.compile(r"</?\s*(system|prompt|instruction|persona)\s*>", re.IGNORECASE),
     "fake xml-style role tag"),
    ("role_override.inst_marker",
     "role_override", "medium",
     re.compile(r"\[\s*(INST|/INST|SYSTEM|/SYSTEM)\s*\]"),
     "[INST] / [SYSTEM] markers"),

    # Delimiter spoofing
    ("delimiter_spoof.chat_delimiter",
     "delimiter_spoof", "medium",
     re.compile(r"<\|\s*(im_start|im_end|endoftext|system|user|assistant)\s*\|>",
                 re.IGNORECASE),
     "OpenAI/Anthropic-style delimiter"),
    ("delimiter_spoof.security_frame",
     "delimiter_spoof", "medium",
     re.compile(r"---\s*(BEGIN|END)\s+UNTRUSTED\b", re.IGNORECASE),
     "tries to spoof curator's own security frame"),

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

# Resource-attack thresholds (not regex-based).
_MAX_LINE_LENGTH = 10_000
_MAX_FILE_SIZE   = 5 * 1024 * 1024     # 5 MB

_PER_PATTERN_CAP = 5


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


def scan(path: Path) -> dict:
    """Scan a file for prompt-injection / security issues.

    Returns a dict with ``verdict``, ``checks`` (every check with
    PASS/FAIL), ``findings`` (capped excerpts of failures), and
    ``summary`` (match counts by category).
    """
    if not path.exists():
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
                "notes":       f"file not found: {path}",
            }],
            "findings": [{
                "category":    "missing_file",
                "severity":    "high",
                "description": f"file not found: {path}",
            }],
            "summary": {"missing_file": 1},
        }

    file_size = path.stat().st_size
    findings: list[dict] = []
    checks:   list[dict] = []

    # ── resource: input exists ───────────────────────────────
    _record_check(
        checks, name="input.exists",
        category="missing_file", severity="high",
        description="input file present and readable",
        matches=0,
    )

    # ── resource: file size ──────────────────────────────────
    file_size_ok = file_size <= _MAX_FILE_SIZE
    _record_check(
        checks, name="resource.file_size",
        category="resource_attack", severity="high",
        description=f"file size <= {_MAX_FILE_SIZE} bytes",
        matches=0 if file_size_ok else 1,
        notes=f"actual: {file_size} bytes",
    )
    if not file_size_ok:
        findings.append({
            "category":    "resource_attack",
            "severity":    "high",
            "description": f"file size {file_size} exceeds limit {_MAX_FILE_SIZE}",
        })

    text = path.read_text(encoding="utf-8", errors="replace")

    # ── resource: line length ────────────────────────────────
    long_lines = [
        (i, len(line)) for i, line in enumerate(text.splitlines(), 1)
        if len(line) > _MAX_LINE_LENGTH
    ]
    _record_check(
        checks, name="resource.line_length",
        category="resource_attack", severity="high",
        description=f"every line <= {_MAX_LINE_LENGTH} chars",
        matches=len(long_lines),
        notes=f"longest line: {max((n for _, n in long_lines), default=0)}",
    )
    for line_no, line_len in long_lines:
        findings.append({
            "category":    "resource_attack",
            "severity":    "high",
            "line":        line_no,
            "description": f"line length {line_len} exceeds {_MAX_LINE_LENGTH}",
        })

    # ── pattern catalog ──────────────────────────────────────
    for name, category, severity, regex, description in _PATTERNS:
        all_matches = list(regex.finditer(text))
        _record_check(
            checks, name=name,
            category=category, severity=severity,
            description=description,
            matches=len(all_matches),
        )
        for m in all_matches[:_PER_PATTERN_CAP]:
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
        if len(all_matches) > _PER_PATTERN_CAP:
            findings.append({
                "category":    category,
                "severity":    severity,
                "name":        name,
                "description": f"{description} — {len(all_matches) - _PER_PATTERN_CAP} additional match(es) truncated",
            })

    # ── derived summary ──────────────────────────────────────
    summary: dict[str, int] = {}
    for f in findings:
        summary[f["category"]] = summary.get(f["category"], 0) + 1

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")

    return {
        "verdict":   "FAIL" if findings else "PASS",
        "ok":        len(findings) == 0,
        "checks":    checks,
        "checks_passed": pass_count,
        "checks_failed": fail_count,
        "findings":  findings,
        "summary":   summary,
        "scanned":   str(path),
        "file_size": file_size,
    }


# ── CLI ─────────────────────────────────────────────────────────

app = typer.Typer(help="Security scan.", no_args_is_help=True)


@app.command("security-scan")
def cli_security_scan(
    path: Annotated[str, typer.Argument(
        help="Absolute path to the converted source markdown.")],
) -> None:
    """Scan source for prompt injection / security issues.

    Emits YAML on stdout. Exits 0 on PASS, 1 on FAIL. Engine treats
    a non-zero exit as task failure; the orchestrator surfaces the
    findings as BLOCKED.
    """
    result = scan(Path(path))
    emit(result)
    if result["verdict"] == "FAIL":
        raise typer.Exit(code=1)

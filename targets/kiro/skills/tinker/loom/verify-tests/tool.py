"""Tool body for the `verify-tests` task (loomv2 native contract).

Resolves `test_cmd_used`: prefer each installed skill's
``scripts/test.sh`` (or a script whose basename matches
``test*.sh``); first match wins. Falls back to
`fallback_test_cmd`. If both are empty, emits `passed = false` and a
stderr note.

The engine loads this module in-process and calls `verify_tests`;
all YAML IO and schema validation is engine-owned.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path
from typing import Any, Optional

from io_types import VerifyTestsInput, VerifyTestsOutput

# 4 KiB — matches io.yaml `stdout_tail` / `stderr_tail` documented cap.
_TAIL_BYTES = 4 * 1024

# 10 minutes — bounds the test run so a stuck process cannot hold the
# pipeline; matches feature-make's original test-timeout convention.
_TIMEOUT_SECONDS = 600


def _skill_test_shim(skill: dict[str, Any]) -> Optional[str]:
    """Return the absolute path to the skill's well-known test shim, if any."""
    scripts_dir = Path(skill["path"]).parent / "scripts"
    scripts = skill.get("scripts") or []
    # Prefer exact `test.sh`; otherwise first `test*.sh`.
    if "test.sh" in scripts:
        return str(scripts_dir / "test.sh")
    for name in scripts:
        if fnmatch.fnmatch(name, "test*.sh"):
            return str(scripts_dir / name)
    return None


def _resolve_test_cmd(installed_skills: list[dict[str, Any]], fallback: str) -> str:
    for skill in installed_skills:
        shim = _skill_test_shim(skill)
        if shim:
            return shim
    return fallback


def _tail(text: str) -> str:
    encoded = text.encode("utf-8", errors="replace")
    if len(encoded) <= _TAIL_BYTES:
        return text
    return encoded[-_TAIL_BYTES:].decode("utf-8", errors="replace")


def verify_tests(inp: VerifyTestsInput) -> VerifyTestsOutput:
    installed_skills = inp.installed_skills or []
    fallback_test_cmd = inp.fallback_test_cmd or ""

    test_cmd_used = _resolve_test_cmd(installed_skills, fallback_test_cmd)

    if not test_cmd_used:
        return VerifyTestsOutput(
            test_cmd_used="",
            exit_code=1,
            passed=False,
            stdout_tail="",
            stderr_tail=(
                f"unresolved test command: build_system={inp.build_system!r} "
                "and no installed-skill test shim available"
            ),
        )

    try:
        proc = subprocess.run(
            test_cmd_used,
            shell=True,
            cwd=inp.workspace_abs,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
        exit_code = proc.returncode
        stdout_tail = _tail(proc.stdout or "")
        stderr_tail = _tail(proc.stderr or "")
    except subprocess.TimeoutExpired as exc:
        exit_code = 124  # matches coreutils `timeout`
        stdout_tail = _tail(exc.stdout.decode("utf-8", errors="replace") if exc.stdout else "")
        stderr_tail = _tail(
            (exc.stderr.decode("utf-8", errors="replace") if exc.stderr else "")
            + f"\ntest command timed out after {_TIMEOUT_SECONDS}s"
        )

    return VerifyTestsOutput(
        test_cmd_used=test_cmd_used,
        exit_code=exit_code,
        passed=exit_code == 0,
        stdout_tail=stdout_tail,
        stderr_tail=stderr_tail,
    )

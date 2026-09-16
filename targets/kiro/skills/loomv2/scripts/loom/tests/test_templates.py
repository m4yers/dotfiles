"""Host-skill SKILL.md templates under templates/.

Renders each fragment through the shared template skill with the
variables SKILL.md documents, pinning the CLI-facing wording so
template↔CLI drift fails here first.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_SKILL_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES = _SKILL_ROOT / "templates"
_RENDER_SH = Path.home() / ".kiro" / "skills" / "home" / "template" / "scripts" / "render.sh"

_VARS = [
    "--var", "prefix=SB",
    "--var", "shim=LOOM",
    "--var", "skill_name=my-skill",
    "--var", "target=<op>",
    "--allow-unused",
]


def _render(name: str) -> str:
    proc = subprocess.run(
        [str(_RENDER_SH), "--template", str(_TEMPLATES / name), *_VARS],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


@pytest.mark.parametrize("name,expected", [
    ("step-drive-loop.md.j2", [
        '$SB_LOOM runtime next "$SB_WD"',
        "runtime complete",
        "done: true",
        "{failed_task, error_path}",
        'my-skill(<op>): Drive the loop',
    ]),
    ("helper-dispatch-agent.md.j2", [
        "$SB_LOOM runtime next",
        "`prompt_path`",
        "`output_path`",
        'runtime complete "$SB_WD"',
    ]),
    ("helper-drive-human-gate.md.j2", [
        "`message_path`",
        "output add",
        'runtime complete "$SB_WD"',
        "$SB_EDITOR show file",
    ]),
])
def test_template_renders_cli_wording(name: str, expected: list[str]):
    out = _render(name)
    for fragment in expected:
        assert fragment in out, f"{name}: missing {fragment!r}"

"""Builds the loom plan for a notepad session.

The plan is a two-task setup (setup-layout -> editor-open) followed by
an interactive two-task loop body:

    command-wait (human gate)   ─┐
        │                          │  latch back-edge until `kind == 'end'`
        v                          │
    command-process (agent)  ────┘

`command-process` runs only when `kind == 'action'`; `question`
commands are handled inline by the main agent. On `kind == 'end'`
the latch's `while` fires false, exiting the loop cleanly.
"""
from __future__ import annotations

from pathlib import Path

from loom import LoomPlan, agent, human, latch, make_plan, tool


# scripts/notepad/plan.py -> parents[2] is the notepad skill root.
SKILL_ROOT = Path(__file__).resolve().parents[2]
NOTEPAD_SH = SKILL_ROOT / "scripts" / "notepad.sh"
PROMPTS    = SKILL_ROOT / "templates" / "prompts"
SCHEMAS    = SKILL_ROOT / "schemas"


def build_plan(workdir: Path, skill_dir: Path) -> LoomPlan:
    """Return the loom plan for a notepad session at `workdir`."""
    notepad_path = "${workdir}/notepad.md"

    return make_plan(
        tool(
            "setup-layout",
            cmd=[str(NOTEPAD_SH), "pipeline", "setup-layout",
                 "--workdir", "${workdir}"],
            output_schema=str(SCHEMAS / "setup-layout.yaml"),
        ),
        tool(
            "editor-open",
            cmd=[str(NOTEPAD_SH), "pipeline", "editor-open",
                 "--workdir", "${workdir}",
                 "--notepad", notepad_path],
            depends_on_all=["setup-layout"],
            output_schema=str(SCHEMAS / "editor-open.yaml"),
        ),
        human(
            "command-wait",
            template=str(PROMPTS / "command-wait.md.j2"),
            output_schema=str(SCHEMAS / "command-wait.yaml"),
            depends_on_all=["editor-open"],
        ),
        agent(
            "command-process",
            template=str(PROMPTS / "command-process.md.j2"),
            output_schema=str(SCHEMAS / "command-process.yaml"),
            depends_on_all=["command-wait"],
            when="${task:command-wait:kind} == 'action'",
            latch=latch(
                "command-wait",
                while_="${task:command-wait:kind} != 'end'",
            ),
        ),
    )

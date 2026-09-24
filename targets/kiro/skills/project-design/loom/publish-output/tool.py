"""Exit task for project-design: verbatim pass-through.

Exists so the subgraph has a single exit whose outputs form the
skill's contract (the approved design artifacts).
"""

from io_types import PublishOutputInput, PublishOutputOutput


def publish_output(inp: PublishOutputInput) -> PublishOutputOutput:
    return PublishOutputOutput(
        design=inp.design,
        decisions=inp.decisions,
        open_risks=inp.open_risks,
        research_report=inp.research_report,
        gate_note=inp.gate_note,
    )

"""load-doc — parse the live-doc file into the stage-grouped structure.

Delegates to :func:`live_doc.vault_io.parse`; fails loudly on any
missing or misordered H2 subsection via ``BadDocShapeError``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from io_types import LoadDocInput, LoadDocOutput

# vault_io lives in the live-doc scripts package; add it to sys.path.
_HERE = Path(__file__).resolve()
_PKG = _HERE.parent.parent.parent / "scripts" / "live-doc"
sys.path.insert(0, str(_PKG))

from live_doc import vault_io  # noqa: E402


def load_doc(inp: LoadDocInput) -> LoadDocOutput:
    text = Path(inp.vault_path).read_text()
    parsed = vault_io.parse(text)
    return LoadDocOutput(
        intro=parsed.intro,
        instructions=parsed.instructions,
        prev_result_header=parsed.result_header,
        prev_result_subsections=[
            {"heading": s.heading, "body": s.body}
            for s in parsed.result_subsections
        ],
        appendix_scripts={
            key: [
                {"name": e.name, "description": e.description,
                 "source": e.source}
                for e in entries
            ]
            for key, entries in parsed.appendix_scripts.items()
        },
        run_order=parsed.run_order,
    )

"""assemble-doc — write the final four-section doc back to the vault.

Delegates to :func:`live_doc.vault_io.assemble`; writes atomically
(tmp + rename) so a crash mid-write cannot leave a half-rewritten
doc on disk.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from io_types import AssembleDocInput, AssembleDocOutput

_HERE = Path(__file__).resolve()
_PKG = _HERE.parent.parent.parent / "scripts" / "live-doc"
sys.path.insert(0, str(_PKG))

from live_doc import vault_io  # noqa: E402


def _to_entries(items):
    return [
        vault_io.ScriptEntry(
            name=d["name"],
            description=d["description"],
            source=d["source"],
        )
        for d in items
    ]


def assemble_doc(inp: AssembleDocInput) -> AssembleDocOutput:
    parts = vault_io.AssembleParts(
        intro=inp.intro,
        instructions=inp.instructions,
        result_header=inp.result_header,
        result_subsections=[
            vault_io.ResultSubsection(heading=s["heading"],
                                      body=s["body"])
            for s in inp.result_subsections
        ],
        appendix_scripts={
            "ingestion": _to_entries(inp.scripts_ingestion),
            "inference": _to_entries(inp.scripts_inference),
            "presentation": _to_entries(inp.scripts_presentation),
        },
        run_order={
            "ingestion": inp.run_order_ingestion,
            "inference": inp.run_order_inference,
            "presentation": inp.run_order_presentation,
        },
    )
    text = vault_io.assemble(parts)
    target = Path(inp.vault_path)
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.",
                               dir=target.parent)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, target)
    return AssembleDocOutput(
        vault_path=str(target),
        bytes_written=len(text.encode()),
    )

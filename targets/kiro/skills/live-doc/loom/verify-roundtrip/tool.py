"""verify-roundtrip — re-parse the just-written doc and assert
stage-grouped script_hash equality and matching result subsection
headings. Any divergence raises before commit-vault runs.
"""
from __future__ import annotations

import sys
from pathlib import Path

from io_types import VerifyRoundtripInput, VerifyRoundtripOutput

_HERE = Path(__file__).resolve()
_PKG = _HERE.parent.parent.parent / "scripts" / "live-doc"
sys.path.insert(0, str(_PKG))

from live_doc import vault_io  # noqa: E402


def _entries(items):
    return [
        vault_io.ScriptEntry(
            name=d["name"],
            description=d["description"],
            source=d["source"],
        )
        for d in items
    ]


def verify_roundtrip(
    inp: VerifyRoundtripInput,
) -> VerifyRoundtripOutput:
    text = Path(inp.vault_path).read_text()
    parsed = vault_io.parse(text)
    expected = {
        "ingestion": _entries(inp.scripts_ingestion),
        "inference": _entries(inp.scripts_inference),
        "presentation": _entries(inp.scripts_presentation),
    }
    exp_hashes = vault_io.script_hash(expected)
    got_hashes = vault_io.script_hash(parsed.appendix_scripts)
    if exp_hashes != got_hashes:
        raise ValueError(
            f"appendix round-trip hash mismatch: "
            f"expected={exp_hashes} got={got_hashes}"
        )
    expected_order = {
        "ingestion": inp.run_order_ingestion,
        "inference": inp.run_order_inference,
        "presentation": inp.run_order_presentation,
    }
    if parsed.run_order != expected_order:
        raise ValueError(
            f"appendix run-order mismatch: expected={expected_order} "
            f"got={parsed.run_order}"
        )
    exp_headings = [s["heading"] for s in inp.result_subsections]
    got_headings = [s.heading for s in parsed.result_subsections]
    if exp_headings != got_headings:
        raise ValueError(
            f"result subsection headings mismatch: "
            f"expected={exp_headings} got={got_headings}"
        )
    return VerifyRoundtripOutput(ok=True)

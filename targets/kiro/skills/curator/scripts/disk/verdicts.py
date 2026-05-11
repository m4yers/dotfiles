"""Aggregate per-attempt judge verdicts into the final verdicts file.

Each judge dispatch writes ``<wd>/verdicts/<kind>-attempt-<N>.json``
per attempt. When the retry loop terminates (ACCEPT/REVIEW reached, or
the 3-attempt budget is exhausted), the orchestrator calls
``aggregate_verdicts(workdir, kind)`` to collapse those files into the
canonical ``<wd>/verdicts/<kind>.json`` that Step 4 and Step 5
consume.

Aggregation rules:

1. The **current** verdict per item is taken from the last attempt
   file that produced one, with one exception:

   * If the last attempt's verdict is REJECT and we have hit the
     3-attempt budget, convert it to REVIEW so the item surfaces to
     the user gate (it cannot be retried further). The original REJECT
     is preserved in ``retry_history`` so the user sees every attempt.

2. ``retry_history`` carries all *prior* attempts (attempt N-1, N-2,
   …, 1) in chronological order. Attempts that failed schema
   validation and never produced a verdict file are represented as
   synthetic entries with ``verdict: "SCHEMA_FAILURE"``.

3. ``attempts`` is the number of attempts actually made (1..3).

4. ``meta`` counts the *current* verdict per item only; retry_history
   does not contribute.

The orchestrator is responsible for informing this module when a
schema failure occurred — see ``schema_failures`` parameter.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


# Maps each extractor kind to its paired extractor output file. Used by
# the cross-file id-pairing check below so aggregation refuses to
# produce a verdict file whose ids disagree with its extractor.
_EXTRACTOR_FILENAME = {
    "summary":  "summary.json",
    "sources":  "sources.json",
    "keywords": "keywords.json",
    "people":   "people.json",
    "models":   "models.json",
}


def _extractor_ids(doc: dict, kind: str) -> set[str]:
    """Return the set of item ids declared in an extractor output.

    summary.json has no items; by convention the summary judge emits
    a single verdict with id "summary" covering the whole payload.
    """
    if kind == "summary":
        return {"summary"}
    if kind == "sources":
        return {x["id"] for x in doc.get("referenced", []) if "id" in x}
    return {x["id"] for x in doc.get("items", []) if "id" in x}


@dataclass(frozen=True)
class SchemaFailure:
    """Marker for an attempt that failed extractor schema validation.

    The judge never ran for that attempt, so there is no per-attempt
    verdict file. The orchestrator records these so aggregation can
    represent them in retry_history.
    """

    attempt: int
    message: str


def aggregate_verdicts(
    workdir: str | Path,
    kind: str,
    attempts_made: int,
    schema_failures: list[SchemaFailure] | None = None,
) -> dict:
    """Collapse per-attempt verdict files into the canonical verdicts file.

    Parameters
    ----------
    workdir : path
        The curator scratch dir for this ingest.
    kind : str
        Extractor kind (``summary`` … ``models``).
    attempts_made : int
        Total attempts expended on this extractor, 1..3.
    schema_failures : list
        Per-attempt records of extractor schema validation failures.
        These attempts have no judge output; they are recorded as
        ``SCHEMA_FAILURE`` entries in retry_history.

    Returns
    -------
    dict
        ``{ok: True, path: <verdicts-file-path>, meta: {...}}`` on
        success. Raises FileNotFoundError if no per-attempt file
        exists and attempts_made > len(schema_failures) (meaning the
        judge *should* have written something but did not).
    """
    wd = Path(workdir).resolve()
    verdicts_dir = wd / "verdicts"
    schema_failures = schema_failures or []
    failed_attempts = {sf.attempt for sf in schema_failures}

    if attempts_made < 1 or attempts_made > 3:
        raise ValueError(f"attempts_made must be 1..3, got {attempts_made}")

    # Collect per-attempt verdict files in attempt order. Attempts that
    # appear in schema_failures are skipped; they have no judge output.
    per_attempt: dict[int, dict] = {}
    for n in range(1, attempts_made + 1):
        if n in failed_attempts:
            continue
        attempt_path = verdicts_dir / f"{kind}-attempt-{n}.json"
        if not attempt_path.exists():
            raise FileNotFoundError(
                f"judge output missing for {kind} attempt {n}: {attempt_path}"
            )
        per_attempt[n] = json.loads(attempt_path.read_text())

    if not per_attempt and attempts_made > len(schema_failures):
        # All attempts failed schema AND the orchestrator didn't
        # record them as such — an invariant violation.
        raise ValueError(
            f"no judge output for {kind} across {attempts_made} attempts, "
            f"and only {len(schema_failures)} schema failures recorded"
        )

    # The "current" verdict per item comes from the most recent judge
    # run that produced one. If all attempts were schema failures we
    # emit an empty verdicts array; the orchestrator should raise the
    # schema failures to the user separately via BLOCKED.
    latest_attempt = max(per_attempt) if per_attempt else None
    latest = per_attempt.get(latest_attempt, {"verdicts": []}) if latest_attempt else {"verdicts": []}

    # Build retry_history per item. For each item in the latest run,
    # collect its entries from attempts < latest_attempt (only from
    # attempts that produced a judge file; schema failures are added
    # at the end as synthetic entries).
    final_verdicts: list[dict] = []
    budget_exhausted = attempts_made >= 3

    for item in latest.get("verdicts", []):
        item_id = item["id"]
        history: list[dict] = []

        # Prior judge attempts for this id.
        for n in sorted(per_attempt):
            if latest_attempt is not None and n >= latest_attempt:
                continue
            prior = _find_item(per_attempt[n], item_id)
            if prior is not None:
                history.append({
                    "attempt": n,
                    "verdict": prior["verdict"],
                    "issues": prior.get("issues", []),
                })

        # Schema failures interleaved by attempt number.
        for sf in sorted(schema_failures, key=lambda x: x.attempt):
            if latest_attempt is not None and sf.attempt >= latest_attempt:
                continue
            history.append({
                "attempt": sf.attempt,
                "verdict": "SCHEMA_FAILURE",
                "issues": [{
                    "severity": "error",
                    "category": "anatomy",
                    "message": sf.message or "extractor output failed schema validation",
                }],
            })

        # Sort by attempt so the reader sees chronological order even
        # when schema failures and judge runs interleave.
        history.sort(key=lambda r: r["attempt"])

        current_verdict = item["verdict"]
        # Exhaustion conversion: REJECT on the final attempt of a
        # full 3-attempt budget becomes REVIEW so the user gate still
        # sees the item.
        if budget_exhausted and current_verdict == "REJECT":
            current_verdict = "REVIEW"

        out_item = {
            "id": item_id,
            "verdict": current_verdict,
            "issues": item.get("issues", []),
        }
        if "rewrite_suggestion" in item:
            out_item["rewrite_suggestion"] = item["rewrite_suggestion"]
        if history:
            out_item["retry_history"] = history
        final_verdicts.append(out_item)

    meta = {
        "items_total": len(final_verdicts),
        "accept": sum(1 for v in final_verdicts if v["verdict"] == "ACCEPT"),
        "review": sum(1 for v in final_verdicts if v["verdict"] == "REVIEW"),
        "reject": sum(1 for v in final_verdicts if v["verdict"] == "REJECT"),
    }

    aggregated = {
        "kind": kind,
        "attempts": attempts_made,
        "verdicts": final_verdicts,
        "meta": meta,
    }

    # Cross-file invariant: every verdict id must match an extractor
    # id. Previously enforced by a separate validate-verdicts call;
    # pushed into the producer so there is a single canonical gate.
    extractor_fname = _EXTRACTOR_FILENAME.get(kind)
    if extractor_fname is None:
        raise ValueError(f"unknown kind: {kind}")
    extractor_path = wd / extractor_fname
    if extractor_path.exists():
        extractor_doc = json.loads(extractor_path.read_text())
        extractor_ids = _extractor_ids(extractor_doc, kind)
        verdict_ids = {v["id"] for v in final_verdicts}
        missing = extractor_ids - verdict_ids
        extra = verdict_ids - extractor_ids
        if missing or extra:
            raise ValueError(
                f"id pairing mismatch for {kind}: "
                f"extractor has {sorted(extractor_ids)}, "
                f"verdicts have {sorted(verdict_ids)}; "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )

    # Schema-check and atomic-write the canonical aggregate. This is
    # a tool-produced file, so the write path is inlined here;
    # pending/promote is not needed. Meta counts and retry_history
    # length are correct by construction (we computed them here).
    out_path = verdicts_dir / f"{kind}.json"
    schema = json.loads((SCHEMA_DIR / "verdict.schema.json").read_text())
    jsonschema.validate(instance=aggregated, schema=schema)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    tmp.write_text(json.dumps(aggregated, ensure_ascii=False, indent=2))
    os.replace(tmp, out_path)

    return {"ok": True, "path": str(out_path), "meta": meta}


def _find_item(verdict_doc: dict, item_id: str) -> dict | None:
    for v in verdict_doc.get("verdicts", []):
        if v.get("id") == item_id:
            return v
    return None

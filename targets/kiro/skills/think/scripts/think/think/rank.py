"""Rank tool task — deterministic weighted aggregation.

Inputs (read from the loom workdir):

- `rubric` output     — for the dimension list and weights.
- `answer-{1,2,3}`    — for headlines and link paths.
- `compare-1v2/3/2v3` — for the pair-wise dimension verdicts.

Output (written via the loom output writer to the rank
task's output.yaml):

- `ranking`              — sorted by score desc; each entry
                           carries the answer id, score, link,
                           and headline.
- `dimension_scores`     — per-dimension breakdown (weight,
                           per-answer averaged 1-5 scores,
                           per-answer weighted contributions,
                           and per-pair winners for audit).
- `confidence_gap`       — (top - runner_up) / max_possible.
                           Informational; never gates.
- `intransitivity_cycles`— count of directed 3-cycles in
                           the pair-win graph. Informational.
- `rejected_judgments`   — compare outputs excluded due to
                           missing evidence. Defense in depth.
- `summary`              — short markdown summary embedded by
                           the report template.

Why deterministic: the formula is fixed; the only variable
is which judgments pass evidence enforcement. Putting this
in an agent would let the model second-guess its own
pair-wise verdicts — exactly the failure mode the
pair-wise step exists to prevent.

Scoring (feature-make adopted):

    averaged[c][d] = mean(score[c][d] across pairs c is in)
    total[c]       = sum(weight[d] * averaged[c][d])
    ranking        = sort(totals, desc)

NO human gates. NO disqualification. NO needs_human flag.
The new signals (intransitivity_cycles, confidence_gap,
rejected_judgments) are surfaced in the report so the user
can decide whether to trust the ranking — they are never
used to block promotion.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

from loom.engine import store as _store
from loom.engine.models import LoomPlan


# All three answer ids. Hard-coded to match plan.py — the
# DAG fans out to exactly three answers, no more, no less.
# Defined here as a single source of truth for ranking
# enumeration and link construction.
_ANSWER_IDS = ["answer-1", "answer-2", "answer-3"]

# All three compare task ids and the pair they judge. Order
# follows plan._COMPARE_PAIRS.
_COMPARE_PAIRS = [
    ("compare-1v2", "answer-1", "answer-2"),
    ("compare-1v3", "answer-1", "answer-3"),
    ("compare-2v3", "answer-2", "answer-3"),
]

# Maximum 1-5 score on the per-dimension anchor scale. The
# max possible weighted total per answer is 5 * sum(weights),
# which is the denominator of `confidence_gap`.
_MAX_SCORE = 5.0


def aggregate(workdir: Path) -> None:
    """Read inputs, compute ranking, write output via loom."""
    rubric  = _load_task_output(workdir, "rubric")
    answers = {aid: _load_task_output(workdir, aid)
               for aid in _ANSWER_IDS}
    compares_raw = {cid: _load_task_output(workdir, cid)
                    for cid, _, _ in _COMPARE_PAIRS}

    dimensions = rubric.get("dimensions", [])
    if not dimensions:
        raise RuntimeError(
            "rubric output has no dimensions; cannot rank")

    dim_names = [d["name"] for d in dimensions]
    weights   = {d["name"]: float(d.get("weight", 0.0))
                 for d in dimensions}

    # Evidence-anchor enforcement (defense in depth on top of
    # compare schema). Rejected compares are excluded from
    # aggregation but recorded for transparency.
    rejected: list[dict] = []
    compares: dict[str, dict] = {}
    for cid, _a, _b in _COMPARE_PAIRS:
        data = compares_raw[cid]
        if _validate_and_record(cid, data, rejected):
            compares[cid] = data

    # Per-answer per-dimension score lists, then averaged.
    averaged = _aggregate_scores(
        compares, dim_names, _COMPARE_PAIRS)

    # Weighted totals.
    totals = _weighted_totals(weights, averaged)

    # Stable ranking: by total desc, then answer id asc.
    ranked = sorted(
        _ANSWER_IDS,
        key=lambda aid: (-totals[aid], aid),
    )

    # Pair-win graph for cycle detection. Pair winner is the
    # majority of dimension `winner` fields — independent of
    # the numeric scores so cycle detection mirrors the
    # agent's own pair-wise verdict, not the aggregator's.
    pair_winners = _pairwise_pair_winners(compares, _COMPARE_PAIRS)
    intransitivity_cycles = _detect_intransitivity(pair_winners)

    # Confidence gap: top vs runner-up over max possible.
    # Informational; never gates promotion.
    max_possible = _MAX_SCORE * sum(weights.values())
    confidence_gap = _confidence_gap(totals, ranked, max_possible)

    # Per-dimension breakdown for transparency / audit.
    dim_breakdown = _build_dim_breakdown(
        compares, dim_names, weights, averaged, _COMPARE_PAIRS)

    # Ranking entries.
    ranking_entries: list[dict] = []
    for aid in ranked:
        ans = answers[aid]
        ranking_entries.append({
            "answer_id": aid,
            "score":     round(totals[aid], 4),
            "link":      str(_task_output_path(workdir, aid)),
            "headline":  str(ans.get("headline", "")),
        })

    summary = _build_summary(
        ranking_entries,
        dim_breakdown,
        confidence_gap,
        intransitivity_cycles,
        rejected,
    )

    _write_output(
        workdir,
        ranking_entries,
        dim_breakdown,
        confidence_gap,
        intransitivity_cycles,
        rejected,
        summary,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_and_record(
    compare_id: str,
    data: dict,
    rejected: list[dict],
) -> bool:
    """Apply evidence-anchor enforcement.

    Returns True if the compare is accepted; False (and
    appends to ``rejected``) if any dimension is missing
    non-empty `evidence_a` or `evidence_b`. Mirrors
    feature-make's scoring._validate_and_record.

    The compare schema also enforces minLength: 1 on
    evidence fields, so in practice loom's output validation
    catches violations upstream and this check is defense in
    depth. When triggered, the offending compare is excluded
    from aggregation and surfaced in `rejected_judgments`.
    """
    bad_dims: list[str] = []
    for d in data.get("dimension_verdicts", []):
        if not d.get("evidence_a") or not d.get("evidence_b"):
            bad_dims.append(d.get("dimension", "<unknown>"))
    if bad_dims:
        rejected.append({
            "compare_id": compare_id,
            "reason":     f"missing evidence on dims: {', '.join(bad_dims)}",
        })
        return False
    return True


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _aggregate_scores(
    compares: dict[str, dict],
    dim_names: list[str],
    compare_pairs: list[tuple[str, str, str]],
) -> dict[str, dict[str, float | None]]:
    """Per-answer per-dimension averaged 1-5 scores.

    Each compare contributes one a_score for answer A and
    one b_score for answer B per dimension. Per answer, the
    scores collected across the pairs the answer appears in
    are averaged; the count normalises so an answer is not
    penalised for appearing in more pairs.

    Missing dimensions or non-numeric scores are skipped;
    the resulting averaged score is None when no scores
    were collected, which contributes 0 to the weighted
    total.
    """
    raw: dict[str, dict[str, list[float]]] = {
        aid: {dn: [] for dn in dim_names} for aid in _ANSWER_IDS
    }
    for cid, a_id, b_id in compare_pairs:
        if cid not in compares:
            continue
        for dv in compares[cid].get("dimension_verdicts", []):
            dn = dv.get("dimension")
            if dn not in dim_names:
                continue
            a_score = dv.get("a_score")
            b_score = dv.get("b_score")
            if isinstance(a_score, (int, float)):
                raw[a_id][dn].append(float(a_score))
            if isinstance(b_score, (int, float)):
                raw[b_id][dn].append(float(b_score))

    averaged: dict[str, dict[str, float | None]] = {}
    for aid, dims in raw.items():
        averaged[aid] = {
            dn: (sum(v) / len(v)) if v else None
            for dn, v in dims.items()
        }
    return averaged


def _weighted_totals(
    weights: dict[str, float],
    averaged: dict[str, dict[str, float | None]],
) -> dict[str, float]:
    """Sum weight * averaged across dimensions per answer."""
    totals: dict[str, float] = {}
    for aid, dims in averaged.items():
        t = 0.0
        for dn, s in dims.items():
            if s is not None:
                t += weights.get(dn, 0.0) * s
        totals[aid] = t
    return totals


# ---------------------------------------------------------------------------
# Pair-win graph and intransitivity
# ---------------------------------------------------------------------------

def _pairwise_pair_winners(
    compares: dict[str, dict],
    compare_pairs: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    """Return list of (pair_id, winner_aid, loser_aid).

    Pair winner = answer with the majority of `winner: a|b`
    fields across dimensions. Ties produce no edge. Mirrors
    feature-make's _pairwise_wins / _detect_intransitivity
    edge construction.
    """
    edges: list[tuple[str, str, str]] = []
    for cid, a_id, b_id in compare_pairs:
        if cid not in compares:
            continue
        a_w = b_w = 0
        for dv in compares[cid].get("dimension_verdicts", []):
            w = str(dv.get("winner", "")).lower()
            if w == "a":
                a_w += 1
            elif w == "b":
                b_w += 1
        if a_w > b_w:
            edges.append((cid, a_id, b_id))
        elif b_w > a_w:
            edges.append((cid, b_id, a_id))
        # Ties: no directed edge — neither answer "won" the pair.
    return edges


def _detect_intransitivity(
    pair_winners: list[tuple[str, str, str]],
) -> int:
    """Count directed 3-cycles in the pair-win graph.

    For N=3 answers the maximum is two (a->b->c->a and its
    reverse traversal of the same cycle). >0 means the
    compares disagree about who is best. Informational only
    — the ranking is still emitted; the report just
    surfaces the count.
    """
    edges: set[tuple[str, str]] = {(w, l) for _cid, w, l in pair_winners}
    nodes = sorted({n for e in edges for n in e})
    cycles = 0
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            for c in nodes:
                if c in (a, b):
                    continue
                if (a, b) in edges and (b, c) in edges and (c, a) in edges:
                    cycles += 1
                if (a, c) in edges and (c, b) in edges and (b, a) in edges:
                    cycles += 1
    return cycles


# ---------------------------------------------------------------------------
# Confidence gap and per-dimension breakdown
# ---------------------------------------------------------------------------

def _confidence_gap(
    totals: dict[str, float],
    ranked: list[str],
    max_possible: float,
) -> float:
    """(top - runner_up) / max_possible, clipped to [0, 1].

    0 when there is no second place or when max_possible is
    zero (no weights). Informational only — never used to
    block promotion.
    """
    if max_possible <= 0 or len(ranked) < 2:
        return 0.0
    gap = totals[ranked[0]] - totals[ranked[1]]
    g = gap / max_possible
    if g < 0:
        return 0.0
    if g > 1:
        return 1.0
    return g


def _build_dim_breakdown(
    compares: dict[str, dict],
    dim_names: list[str],
    weights: dict[str, float],
    averaged: dict[str, dict[str, float | None]],
    compare_pairs: list[tuple[str, str, str]],
) -> list[dict]:
    """Per-dimension audit table for the rank output."""
    breakdown: list[dict] = []
    for dn in dim_names:
        weight = weights.get(dn, 0.0)
        per_avg: dict[str, float | None] = {
            aid: averaged[aid].get(dn) for aid in _ANSWER_IDS
        }
        per_weighted: dict[str, float] = {
            aid: round(weight * v, 4) if isinstance(v, (int, float))
                 else 0.0
            for aid, v in per_avg.items()
        }
        winners_per_pair: list[dict] = []
        for cid, _a, _b in compare_pairs:
            winner = ""
            if cid in compares:
                for dv in compares[cid].get("dimension_verdicts", []):
                    if dv.get("dimension") == dn:
                        winner = str(dv.get("winner", "")).lower()
                        break
            winners_per_pair.append({"pair": cid, "winner": winner})

        breakdown.append({
            "dimension":           dn,
            "weight":              weight,
            "per_answer_averaged": {
                aid: (round(v, 4) if isinstance(v, (int, float)) else None)
                for aid, v in per_avg.items()
            },
            "per_answer_weighted": per_weighted,
            "winners_per_pair":    winners_per_pair,
        })
    return breakdown


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _build_summary(
    ranking: list[dict],
    dims: list[dict],
    confidence_gap: float,
    intransitivity_cycles: int,
    rejected: list[dict],
) -> str:
    """Compact markdown summary embedded in the final report.

    Surfaces the new informational signals so the report
    reader sees them even without scrolling to the
    Confidence signals section. None of these are gates;
    they are inputs the user weighs when deciding whether
    to trust the ranking.
    """
    lines: list[str] = []
    if ranking:
        winner = ranking[0]
        lines.append(
            f"Top-ranked answer: **{winner['answer_id']}** "
            f"(score {winner['score']}). "
            f"_{winner['headline']}_"
        )
    if len(ranking) > 1:
        gap = ranking[0]["score"] - ranking[1]["score"]
        lines.append(
            f"Gap to second place: {round(gap, 4)} weighted points "
            f"across {len(dims)} dimensions "
            f"(confidence_gap = {round(confidence_gap, 4)} of max)."
        )
    signals: list[str] = []
    if intransitivity_cycles > 0:
        signals.append(
            f"intransitivity_cycles = {intransitivity_cycles} "
            f"(compares disagree about a strict order)"
        )
    if rejected:
        signals.append(
            f"rejected_judgments = {len(rejected)} "
            f"(missing evidence)"
        )
    if signals:
        lines.append("Informational signals: " + "; ".join(signals) + ".")
    return "\n\n".join(lines) if lines else ""


# ---------------------------------------------------------------------------
# Loom plumbing
# ---------------------------------------------------------------------------

def _load_plan(workdir: Path) -> LoomPlan:
    """Load plan.yaml from the loom workdir."""
    return _store.load_plan(workdir)


def _task_output_path(workdir: Path, task_id: str) -> Path:
    """Resolve a task's output.yaml via loom's numbered layout."""
    plan = _load_plan(workdir)
    return _store.task_output_path(workdir, plan, task_id)


def _load_task_output(workdir: Path, task_id: str) -> dict[str, Any]:
    p = _task_output_path(workdir, task_id)
    if not p.exists():
        raise FileNotFoundError(
            f"task output missing: {p} (task_id={task_id})")
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _write_output(
    workdir: Path,
    ranking: list[dict],
    dim_breakdown: list[dict],
    confidence_gap: float,
    intransitivity_cycles: int,
    rejected: list[dict],
    summary: str,
) -> None:
    """Persist via the loom output writer.

    Going through the writer keeps schema validation eager
    and the on-disk YAML normalised, matching how every
    other tool task in the project produces its output.
    """
    loom_sh = os.environ.get("LOOM_SH")
    if not loom_sh:
        skills_root = Path(
            os.environ.get(
                "SKILLS", os.path.expanduser("~/.kiro/skills")))
        loom_sh = str(
            skills_root / "home" / "loom" / "scripts" / "loom.sh")

    def run(args: list[str]) -> None:
        subprocess.run(args, check=True)

    run([loom_sh, "output", "init", str(workdir), "--task", "rank"])

    sets: list[str] = []

    # ranking[]
    for i, entry in enumerate(ranking):
        sets += [
            "--set", f"ranking.{i}.answer_id={entry['answer_id']}",
            "--set", f"ranking.{i}.score={entry['score']}",
            "--set", f"ranking.{i}.link={entry['link']}",
            "--set", f"ranking.{i}.headline={entry['headline']}",
        ]

    # dimension_scores[]
    for di, db in enumerate(dim_breakdown):
        sets += [
            "--set", f"dimension_scores.{di}.dimension={db['dimension']}",
            "--set", f"dimension_scores.{di}.weight={db['weight']}",
        ]
        for aid, val in db["per_answer_averaged"].items():
            v = "null" if val is None else str(val)
            sets += [
                "--set",
                f"dimension_scores.{di}.per_answer_averaged.{aid}={v}",
            ]
        for aid, val in db["per_answer_weighted"].items():
            sets += [
                "--set",
                f"dimension_scores.{di}.per_answer_weighted.{aid}={val}",
            ]
        for wi, w in enumerate(db["winners_per_pair"]):
            sets += [
                "--set",
                f"dimension_scores.{di}.winners_per_pair.{wi}.pair={w['pair']}",
                "--set",
                f"dimension_scores.{di}.winners_per_pair.{wi}.winner={w['winner']}",
            ]

    # informational signals
    sets += [
        "--set", f"confidence_gap={round(confidence_gap, 4)}",
        "--set", f"intransitivity_cycles={intransitivity_cycles}",
    ]

    # rejected_judgments[]
    for ri, rj in enumerate(rejected):
        sets += [
            "--set", f"rejected_judgments.{ri}.compare_id={rj['compare_id']}",
            "--set", f"rejected_judgments.{ri}.reason={rj['reason']}",
        ]

    sets += ["--set", f"summary={summary}"]

    run([loom_sh, "output", "add", str(workdir),
         "--task", "rank", *sets])

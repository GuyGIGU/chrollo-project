"""Election-trace export — the walk's own narration as a published artifact.

``read_structure(trace=[...])`` already narrates the whole walk (the
explainability rule); this module is the ONE owner of what leaves the engine.
Three laws, each paid for:

- **Same-run capture.** The export summarizes the trace captured during the
  very election that produced the published box (evaluation passes ``trace=[]``
  under the flag). Never re-invoke the cascade to regenerate a story — a
  re-run on a fresher frame can elect a different box and explain an election
  that never fired.
- **The raw trace never leaves.** Measured 2026-08-04 over 40 real fires:
  full-trace JSON median ~106 KB, p90 3.6 MB, max 5.8 MB per ticker — the
  internal records (window-relative history, freely-refactorable slots) are
  not a wire contract. This exporter emits ONE compact, date-anchored,
  closed-set shape; changing it is a seam event, never a silent key edit.
- **Sentences render from numbers.** The operator-facing wording derives from
  the structured gate-leg records (``box_gates.GATE_LEGS``) through the ONE
  vocabulary below — internal ``detail`` prose (settings-constant names,
  engineer jargon) never reaches a surface.

The archive stores the export as ONE TEXT cell (``election_trace``, model-only
column) so verdicts the operator records against a shown trace stay bound to
the evidence he actually saw (re-deriving under a rotated engine produces a
different trace). NULL = never captured (flag off / pre-flip rows).
"""
from __future__ import annotations

import json

import pandas as pd

from engine_alpha.structure.box_gates import GATE_LEG_INDEX
from engine_alpha.structure.box_trace import CASCADE_STAGES

__all__ = [
    "ELECTION_TRACE_COLUMN_SQL",
    "election_trace_archive_values",
    "election_trace_chart_fields",
    "export_election_trace",
    "leg_sentence",
    "terminal_verdict",
]

# Cascade depth — how far a candidate got before dying — DERIVED from the one
# owning stage declaration (box_trace.CASCADE_STAGES), never hand-typed here:
# the hand-typed subset this replaced shipped drifted on day one, missing the
# two POLICY kills ("rescue_unused"/"dethroned" — rejected verdicts stamped by
# the producer on framings that had already passed every gate) and ranking
# them below a width death (council review 2026-08-05, finding 9).
_STAGE_DEPTH = {stage: depth for depth, stage in enumerate(CASCADE_STAGES)}

# Operator-language phrasing per gate leg (strategy_alpha's explainability rule:
# trace labels speak plain chart language where humans read). {m} = measured,
# {t} = threshold, both formatted in the leg's native quantum. Real chart
# words only — no retired jargon, no settings-constant names.
_LEG_PHRASES = {
    "width": "box height {m} of price vs cap {t}",
    "window": "window {m} bars vs floor {t}",
    "respect_share": "share of bars respecting the rails {m} vs floor {t}",
    "respect_run": "longest run outside the rails {m} bars vs cap {t}",
    "crash": "low vs support {m} vs crash floor {t}",
    "r_touches": "resistance touches {m} vs floor {t}",
    "s_touches": "support touches {m} vs floor {t}",
    "r_touch_thirds": "window thirds touching resistance {m} vs floor {t}",
    "s_touch_thirds": "window thirds touching support {m} vs floor {t}",
    "lower_dwell": "time in the lower third {m} vs floor {t}",
    "upper_dwell": "time in the upper third {m} vs floor {t}",
    "mid_dwell": "time in the middle third {m} vs cap {t}",
    "coverage": "window occupancy {m} vs floor {t}",
    "traversal_count": "rail-to-rail traversals {m} vs floor {t}",
    "traversal_density": "traversals per swing {m} vs floor {t}",
}


def _fmt(value, quantum: str) -> str:
    """A leg number in its native quantum. None = a declared kill-site unknown
    (the cascade short-circuited before the number existed) — shown as an
    em-dash, never fabricated."""
    if value is None:
        return "—"
    if quantum in ("bars", "touches", "thirds", "traversals"):
        try:
            return str(int(value))
        except (TypeError, ValueError):
            return str(value)
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_pair(measured, threshold, quantum: str) -> tuple[str, str]:
    """Format a measured/threshold PAIR so a real difference never renders as
    equality (council review 2026-08-05, finding 9: a respect share of 0.798
    against floor 0.80 rendered "0.80 vs 0.80" — a refusal sentence whose
    numbers read as a pass, on exactly the near-threshold kills the operator
    inspects). Fraction/ratio quanta widen precision until the two strings
    differ; integer quanta stay ints — their measured values are true counts."""
    if quantum in ("bars", "touches", "thirds", "traversals"):
        return _fmt(measured, quantum), _fmt(threshold, quantum)
    try:
        m, t = float(measured), float(threshold)
    except (TypeError, ValueError):
        return _fmt(measured, quantum), _fmt(threshold, quantum)
    m_str, t_str = f"{m:.2f}", f"{t:.2f}"
    decimals = 2
    while m_str == t_str and m != t and decimals < 6:
        decimals += 1
        m_str, t_str = f"{m:.{decimals}f}", f"{t:.{decimals}f}"
    return m_str, t_str


def leg_sentence(leg_rec: dict) -> str:
    """ONE plain-language sentence for a structured gate-leg record — derived
    from the record's NUMBERS + the leg registry, never from ``detail`` prose.
    An unknown leg id renders honestly as itself (render-verbatim fallthrough,
    never a blank)."""
    leg = leg_rec.get("leg")
    spec = GATE_LEG_INDEX.get(leg)
    phrase = _LEG_PHRASES.get(leg)
    if spec is None or phrase is None:
        m_str, t_str = _fmt_pair(leg_rec.get("measured"),
                                 leg_rec.get("threshold"), "ratio")
        return f"{leg}: {m_str} vs {t_str}"
    m_str, t_str = _fmt_pair(leg_rec.get("measured"),
                             leg_rec.get("threshold"), spec.quantum)
    return phrase.format(m=m_str, t=t_str)


def terminal_verdict(cascade) -> dict:
    """THE summarizer: did this framing's cascade pass, and if not, which
    stage/legs killed the candidate that got furthest? New surfaces consume
    this function, never another copy. KNOWN DEBT (tracked in
    docs/BACKLOG_2026-07.md): the pre-existing census/evidence tools still
    carry three independent re-derivations of this judgment — fold them onto
    this function (or pin equivalence in a check battery) before the next
    consumer lands, else the evidence reports and the operator-facing trace
    can tell different stories about one cascade.

    Furthest = the rejected record with the deepest stage (later record wins
    ties — the cascade walks candidates in order, so a later same-stage death
    is the more-refined framing)."""
    for rec in cascade or []:
        if rec.get("verdict") == "elected":
            return {"passed": True}
    best, best_depth = None, -1
    for rec in cascade or []:
        if rec.get("verdict") != "rejected":
            continue
        # A stage missing from the registry means a NEW cascade stage shipped
        # without registering in CASCADE_STAGES — rank it DEEPEST so it
        # surfaces as the terminal story (loud), never buried below width.
        depth = _STAGE_DEPTH.get(rec.get("stage"), len(CASCADE_STAGES))
        if depth >= best_depth:
            best, best_depth = rec, depth
    if best is None:
        return {"passed": False, "stage": None, "sentences": []}
    legs = list(best.get("legs") or [])
    return {
        "passed": False,
        "stage": best.get("stage"),
        "sentences": [leg_sentence(leg) for leg in legs],
    }


def export_election_trace(trace, df):
    """The outbound artifact for one evaluation's walk: per-root story lines
    (climax/AR dates, outcome, per-stage refusal counts, how far the best
    candidate got) plus the elected framing's provenance. Anchors are DATES
    from the evaluation frame, converted exactly once, here — a bar index is
    frame-relative data and never crosses the wire. Returns None when there
    is nothing to narrate."""
    if not trace:
        return None

    def _date(bar):
        try:
            b = int(bar)
        except (TypeError, ValueError):
            return None
        if b < 0 or b >= len(df):
            return None
        idx = df.index[b]
        return str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]

    roots, elected = [], None
    for rec in trace:
        cascade = rec.get("box_cascade") or []
        refused: dict[str, int] = {}
        for c in cascade:
            if c.get("verdict") == "rejected":
                stage = c.get("stage") or "unknown"
                refused[stage] = refused.get(stage, 0) + 1
        # The fired root narrates the RESOLVED Phase A (the climax→AR bridge
        # the chart overlay draws and the strategy read measures against);
        # died roots keep the seed swing — the honest narration of the walk
        # (council review 2026-08-05, finding 9: seed dates on the fired root
        # disagreed with the drawn Phase-A on the same screen).
        entry = {
            "climax": _date(rec.get("resolved_climax_bar", rec.get("climax_bar"))),
            "ar": _date(rec.get("resolved_ar_bar", rec.get("ar_bar"))),
            "kind": rec.get("kind"),
            "outcome": rec.get("outcome"),
            "candidates": len(cascade),
            "refused": refused,
        }
        # For a root that died at the box election, say how far the best
        # candidate got (a no_lps root's cascade PASSED — the walk died at
        # Phase D, which the outcome already states plainly).
        if rec.get("outcome") == "no_box":
            entry["furthest"] = terminal_verdict(cascade)
        roots.append(entry)

        if rec.get("outcome") == "complete" and elected is None:
            e = next((c for c in cascade if c.get("verdict") == "elected"), None)
            box = rec.get("box") or {}
            # "start" anchors to the PUBLISHED geometry (the box's own
            # start_bar — back-extension included), never the elected
            # record's raw cand_start: whenever the start was walked left to
            # a shared-rail pivot the raw value names a date the drawn box
            # contradicts (council review 2026-08-05, finding 9).
            elected = {
                "root_index": int(rec.get("root_index", len(roots) - 1)),
                "start": _date(box.get("start_bar", (e or {}).get("cand_start"))),
                "R": (e or {}).get("R", box.get("R")),
                "S": (e or {}).get("S", box.get("S")),
                "n_candidates": len(cascade),
                "n_valid": sum(1 for c in cascade
                               if c.get("verdict") in ("valid", "elected")),
                "rescued": bool((e or {}).get("rescued")),
            }
            backext = (e or {}).get("backext_bars")
            if backext:
                # Let the story say the start was walked left, and how far.
                elected["backext_bars"] = int(backext)
    return {"roots": roots, "elected": elected}


# ── Archive column family: the captured narration ────────────────────────────
# Owning declaration (the EVENT_MAP_COLUMN_SQL precedent): ONE TEXT cell, the
# compact export as JSON. MODEL-ONLY add on the ORM model — never hand-listed
# in the writer's _NEW_COLUMNS or startup._MIGRATIONS. NULL = never captured
# (flag off / pre-flip rows), and pre-flip NULLs are never backfilled: a trace
# re-derived under a rotated engine is not the evidence the operator saw.
ELECTION_TRACE_COLUMN_SQL: dict[str, str] = {
    "election_trace": "TEXT",
}


def election_trace_archive_values(get, *, prefixed: bool) -> dict:
    """Row -> {column: value} for the trace family (the writers splat this,
    live prefixed / seed unprefixed — same contract as the event_map family)."""
    value = get("_election_trace" if prefixed else "election_trace")
    if value is not None:
        try:
            if pd.isna(value):
                value = None
        except (TypeError, ValueError):
            pass
    return {"election_trace": value}


def election_trace_chart_fields(get) -> dict:
    """The payload projection: same extraction, with the JSON cell parsed once
    engine-side so the wire carries structure. An unparseable cell degrades to
    None — with the narrative scalars living in their own family, a broken
    trace can never masquerade as an unmeasured story."""
    out = election_trace_archive_values(get, prefixed=True)
    raw = out["election_trace"]
    if raw is not None:
        try:
            out["election_trace"] = json.loads(raw)
        except (TypeError, ValueError):
            out["election_trace"] = None
    return out

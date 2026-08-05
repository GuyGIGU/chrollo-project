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

__all__ = [
    "ELECTION_TRACE_COLUMN_SQL",
    "election_trace_archive_values",
    "election_trace_chart_fields",
    "export_election_trace",
    "leg_sentence",
    "terminal_verdict",
]

# Cascade depth — how far a candidate got before dying. "story" is the
# last-resort pool's own admission stage; "rescue_unused"/"selection" annotate,
# they never kill.
_STAGE_DEPTH = {"width": 0, "window": 1, "respect": 2, "occupancy": 3,
                "traversal": 4, "story": 5}

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


def leg_sentence(leg_rec: dict) -> str:
    """ONE plain-language sentence for a structured gate-leg record — derived
    from the record's NUMBERS + the leg registry, never from ``detail`` prose.
    An unknown leg id renders honestly as itself (render-verbatim fallthrough,
    never a blank)."""
    leg = leg_rec.get("leg")
    spec = GATE_LEG_INDEX.get(leg)
    phrase = _LEG_PHRASES.get(leg)
    if spec is None or phrase is None:
        return (f"{leg}: {_fmt(leg_rec.get('measured'), 'ratio')} vs "
                f"{_fmt(leg_rec.get('threshold'), 'ratio')}")
    return phrase.format(m=_fmt(leg_rec.get("measured"), spec.quantum),
                         t=_fmt(leg_rec.get("threshold"), spec.quantum))


def terminal_verdict(cascade) -> dict:
    """THE summarizer: did this framing's cascade pass, and if not, which
    stage/legs killed the candidate that got furthest? One implementation —
    the census/evidence instruments re-derive this independently today; new
    surfaces consume this function, never a fourth copy.

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
        depth = _STAGE_DEPTH.get(rec.get("stage"), -1)
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
        entry = {
            "climax": _date(rec.get("climax_bar")),
            "ar": _date(rec.get("ar_bar")),
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
            elected = {
                "root_index": int(rec.get("root_index", len(roots) - 1)),
                "start": _date((e or {}).get("cand_start", box.get("start_bar"))),
                "R": (e or {}).get("R", box.get("R")),
                "S": (e or {}).get("S", box.get("S")),
                "n_candidates": len(cascade),
                "n_valid": sum(1 for c in cascade
                               if c.get("verdict") in ("valid", "elected")),
                "rescued": bool((e or {}).get("rescued")),
            }
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

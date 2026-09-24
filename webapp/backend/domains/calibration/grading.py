"""Grading one calibration mark against the engine: the election grade and the
fired walk.

The ONE implementation behind both the agreement harness
(``python -m tools.calibration.calibration_harness``) and the ledger's Engine
chips (``domains.calibration.agreement`` and ``domains.calibration.fired``), so
a chip can never drift from the harness's report. It left the harness for this
production home on 2026-09-24, so the backend no longer imports ``tools/``.

``grade_one`` verifies the frozen frame's digest BEFORE scoring (basis first),
resolves the engine read at the mark's as-of with the frozen day-snap policy
(``core.calibration.replay.snapped_election``; changing snap semantics is a
deliberate re-freeze event, not a knob) and grades it through the pure taxonomy
(``core.calibration.agreement``). All rule variants run in ONE walk per mark.

``fired_one`` (v2) replays a BOX mark through the FULL nightly pipeline
(``_evaluate_ticker`` — the marks-corpus gate's exact decision) over the mark's
fair window, answering the operator's actual satisfaction bar: would this pick
have popped up on the screener in real trading time? Deep ``knowable_from``
walks are clamped to the frame's faithful-basis zone (the clamp is named in the
fragment) so a thin-basis no-fire can never pose as an assessed miss.

Read-only by construction: frames load through the digest-resolved frame store
(frozen-or-refuse, never a vendor fetch) and flag overrides self-restore. This
module loads pandas and the engine at import, so backend code imports it inside
the function that needs it — the FastAPI boot stays engine-free.
"""
from __future__ import annotations

from collections import Counter

import pandas as pd

from config import settings
from core.calibration import agreement, replay
from engine_alpha.election_identity import (
    DEFAULT_RAIL_TOL_BOX_FRAC,
    projection,
    rails_match,
)

# The day-snap policy is OWNED by the replay seam (one value, every
# instrument): re-exported here for grade_one and for report stamping.
SNAP_BACK_SESSIONS = replay.SNAP_BACK_SESSIONS


def _mark_dict(mark) -> dict:
    """ORM row -> the COMPLETE model-shaped dict the shared judgment expects.

    Complete by contract (EC-3): every content column of the mark and its
    events rides through, so the read-side judgment sees exactly what the
    write side validated — dropping a column here silently skips its rules
    (the band omission refused every mini-consolidation batch; the trigger
    omission let the whole trigger rule-family pass unexamined). The SEAL
    does not hash this dict directly: the harness's ``marks_fingerprint``
    projects it onto a FROZEN recipe, so completing this dict never rotates a
    pin.
    """
    d = {c: getattr(mark, c) for c in (
        "ticker", "as_of_date", "label", "verdict", "resistance", "support",
        "box_start_date", "box_end_date", "r_anchor_date", "s_anchor_date",
        "first_rail", "rails_source", "knowable_from_date",
        "note", "data_regime", "engine_config_version", "anchor_close",
        "frame_digest", "trigger_date", "trigger_price")}
    # Events canonicalized by (type, start, end): the ORM returns children in
    # rowid order, and an edit delete-reinserts them in redraw order, so an
    # unsorted list would let a semantically-null redraw move the marks
    # fingerprint (the EC-9 seal) without the ground truth changing. Grading
    # never reads event order, so this only stabilizes the seal.
    d["events"] = [{
        "event_type": e.event_type, "start_date": e.start_date,
        "end_date": e.end_date, "tip_date": e.tip_date,
        "tip_price": e.tip_price, "band_high": e.band_high,
        "band_low": e.band_low, "source": e.source,
    } for e in sorted(mark.events, key=lambda e: (
        e.event_type or "", e.start_date or "", e.end_date or ""))]
    return d


def _vetoed_cause_absent(df, atr, variant: dict) -> bool:
    """Did read_structure elect nothing on THIS frame because the
    cause-before-effect veto fired? Reads the engine's OWN terminal trace
    outcome under the variant's flags — never a re-implementation of the
    veto predicate. Cheap: only consulted for a box mark that already read
    None, and the pivot walk it drives is the same one the election ran."""
    from engine_alpha.structure.narrative.reader import read_structure  # noqa: PLC0415

    trace: list = []
    with replay.flag_capture(**variant):
        read_structure(df, atr, trace=trace)
    return any(r.get("outcome") == "cause_absent" for r in trace)


def grade_one(mark: dict, variants: list[dict], *, frame_loader=None,
              election=replay.snapped_election) -> list[dict]:
    """One mark graded under every variant (ONE snapped walk). Returns one
    row per variant: {outcome, ..., snapped, eval_session}."""
    from webapp.backend import frame_store

    # Digest-resolved load: the store returns whichever frozen rendering
    # matches THIS mark's digest (the base freeze, or the restatement sibling
    # it was actually drawn on) — a mark is never silently replayed on bars
    # its rails weren't drawn against.
    loader = frame_loader or frame_store.load_frame
    frozen = loader(mark["ticker"], mark["as_of_date"],
                    digest=mark.get("frame_digest"))
    if frozen is None:
        return [agreement.ungraded("basis_mismatch",
                                   "no frozen frame matches this mark's digest — "
                                   "the frame store lost its basis")
                for _ in variants]

    # Negative verdicts assert "the engine reads nothing at THIS session" and
    # are graded there only (snap 0). The snap-back walk exists for box
    # verdicts — day-sensitive elections must be shown where they EXIST;
    # hunting prior sessions to convict a negative would bias
    # upheld_over_negatives on days the operator asserted nothing about.
    # Changing either policy is a deliberate re-freeze event.
    snap = SNAP_BACK_SESSIONS if mark["verdict"] == "box" else 0
    snapped = election(frozen, mark["as_of_date"], variants, snap_back=snap)
    if snapped is None:
        # Move 4: name WHICH gate refused each candidate session instead of
        # a bare guess — report-only, never a grading input.
        idx = frozen.index[frozen.index <= pd.Timestamp(mark["as_of_date"])]
        refused = replay.refusal_scan(frozen, idx[-(snap + 1):])
        rows = [agreement.ungraded("edge_uncertain",
                                   "prep refuses every candidate session")
                for _ in variants]
        if refused:
            pr = _refusal_fragment(refused, min(snap + 1, len(idx)))
            for r in rows:
                r["prep_refusals"] = pr
        return rows
    (df, atr, reads), eval_ts, snapped_k = snapped
    frame_start = df.index[0].strftime("%Y-%m-%d")
    rows = []
    for variant, read in zip(variants, reads):
        # A box that elects nothing may have been VETOED (cause-before-effect)
        # rather than plainly unread — re-read this frame under the variant's
        # flags with a trace and consult the engine's OWN cause_absent outcome,
        # so the report attributes the drop (never a re-derivation of the veto).
        vetoed = (mark["verdict"] == "box" and read is None
                  and _vetoed_cause_absent(df, atr, variant))
        g = agreement.grade_mark(mark, projection(read, df),
                                 frame_start=frame_start, vetoed=vetoed)
        g.update({"eval_session": eval_ts.strftime("%Y-%m-%d"),
                  "snapped": snapped_k})
        rows.append(g)
    return rows


# ---------------------------------------------------------------- fired (v2)
# The pops-up-live criterion (operator doctrine 2026-07-11): his bar is the
# ticker appearing in the nightly screener output, so the walk runs the FULL
# eval chain — structure, LPS, gates, scoring — not just the election. Opt-in
# (--fired) because a full eval costs ~1s/session; the walk is bounded and
# the report stamps the bound.
# The fired-policy window is OWNED by the replay seam (one policy, every
# instrument — the marks-corpus ratchet grades the same criterion since the
# Guided List graduation 2026-07-24): re-exported here only for report
# stamping, exactly like SNAP_BACK_SESSIONS above.
FIRED_WINDOW_SESSIONS = replay.FIRED_WINDOW_SESSIONS

# Harness grading-policy version (Family-7 instrument fix, plan task 1).
# v2: the fired-walk is anchored to where the setup was LIVE — the union of
# each marked-LPS event window (+ a small tail) and the trailing as-of window
# — instead of only the sessions before the mark was typed; rail/span
# agreement is additionally graded AT the fire session from that session's
# own read; a post-fire as-of no-read is labeled "consumed", never counted
# as blindness. Bump this on ANY grading-semantics change: it is folded into
# the backend chip cache signature, so stale chips can never be served as
# current after the policy moves (engine hash alone would not rotate).
# v3: the reject-slug vocabulary rotation (Purity task 13) — the LPS diagnose
# counters now speak plain chart language; the bump keeps mixed old/new slug
# vocabulary from ever serving out of the in-process fired-chip cache.
HARNESS_POLICY_VERSION = 3
FIRED_EVENT_TAIL_SESSIONS = replay.FIRED_EVENT_TAIL_SESSIONS
FIRED_WALK_MAX_SESSIONS = replay.FIRED_WALK_MAX_SESSIONS

# Frozen market scalars (scoring-only; they shape Score/Tier, never the
# fire/no-fire decision) — OWNED by the replay seam beside the fired-policy
# constants so the gate and the harness can never drift apart; re-exported
# here only for report stamping, exactly like the window constants above.
_FROZEN_BREADTH = replay.FROZEN_BREADTH
_FROZEN_SPY_6M = replay.FROZEN_SPY_6M


def _refusal_fragment(refused: list, walked: int) -> dict:
    """The Move-4 refusal-telemetry fragment — ONE shape for both report
    paths (graded rows and the fired walk), so the printer can never read
    two spellings of the same evidence."""
    return {"refused": len(refused), "walked": walked,
            "reasons": dict(Counter(slug for _, slug in refused)),
            "sessions": [s for s, _ in refused]}


def _fired_sessions(frozen: pd.DataFrame, mark: dict) -> tuple[list, str | None]:
    """The mark's fair window as frame sessions ending at its as-of.

    Thin adapter over the ONE fired-policy window in the replay seam
    (``replay.fired_window_sessions`` — moved there verbatim 2026-07-24 so the
    marks-corpus ratchet grades the SAME pops-up-live criterion): this wrapper
    only extracts the mark dict's LPS spans and knowable_from override."""
    spans = [(ev["start_date"], ev.get("end_date") or ev["start_date"])
             for ev in mark.get("events") or []
             if ev.get("event_type") == "lps" and ev.get("start_date")]
    return replay.fired_window_sessions(frozen, mark["as_of_date"], spans,
                                        mark.get("knowable_from_date"))


def _binding_gate_margin(result: dict) -> dict | None:
    """Signed distance-to-boundary of the TIGHTEST worked-equilibrium gate on
    a firing result (positive = survived by that much, in the gate's own
    statistic), from the measure-first telemetry fields. None on older result
    shapes without them. Diagnostic only — never a verdict."""
    checks = (
        ("respect", result.get("_eq_respect_frac"),
         settings.MIN_BOUNDARY_RESPECT_PCT, 1),
        ("lower_dwell", result.get("_eq_close_lower_dwell"),
         settings.EQ_MIN_HALF_DWELL, 1),
        ("upper_dwell", result.get("_eq_close_upper_dwell"),
         settings.EQ_MIN_HALF_DWELL, 1),
        ("mid_dwell", result.get("_eq_close_mid_dwell"),
         settings.EQ_MAX_MID_DWELL, -1),
    )
    margins = [{"gate": gate, "margin": round(sign * (float(value) - threshold), 4)}
               for gate, value, threshold, sign in checks if value is not None]
    return min(margins, key=lambda m: m["margin"]) if margins else None


def fired_one(mark: dict, variants: list[dict], *, frame_loader=None,
              evaluate=None) -> list:
    """One BOX mark through the FULL pipeline, per variant (harness v2).

    Non-box marks return None fragments: a negative asserts a no-read at ONE
    session and keeps its election-level grade — window-hunting sessions to
    convict a negative would bias it (the grade_one policy, held here too).

    Returns one fragment per variant: ``fired`` True/False/None(unassessable)
    plus diagnostics. Sessions whose frozen lead-in cannot reproduce the live
    daily-structure basis are clamped OUT of the walk and the clamp named in
    the fragment; inside that faithful zone the pipeline's own floors decide
    — the walk never second-guesses the eval.
    """
    if mark["verdict"] != "box":
        return [None for _ in variants]

    from webapp.backend import frame_store
    from engine_alpha.evaluation import EVAL_ERROR

    if evaluate is None:
        from engine_alpha.evaluation import _evaluate_ticker

        def evaluate(ticker, sliced):
            return _evaluate_ticker(ticker, sliced, _FROZEN_SPY_6M, _FROZEN_BREADTH)

    loader = frame_loader or frame_store.load_frame
    frozen = loader(mark["ticker"], mark["as_of_date"],
                    digest=mark.get("frame_digest"))
    if frozen is None:
        return [{"fired": None, "fired_detail": "basis_mismatch — no frozen "
                                                "frame matches this mark's digest"}
                for _ in variants]
    sessions, clamp_note = _fired_sessions(frozen, mark)
    if not sessions:
        return [{"fired": None,
                 "fired_detail": "no frame sessions inside the fair window"}
                for _ in variants]
    window = [sessions[0].strftime("%Y-%m-%d"), sessions[-1].strftime("%Y-%m-%d")]

    fragments = []
    refusals = None   # variant-independent; scanned ONCE, on the first no-fire
    for variant in variants:
        frag: dict = {"fired": False, "fired_window": window,
                      "fired_sessions_walked": len(sessions)}
        with replay.flag_capture(**variant):
            for ts in sessions:
                result = evaluate(mark["ticker"], frozen.loc[:ts])
                if result is EVAL_ERROR:
                    frag = {"fired": None, "fired_window": window,
                            "fired_detail": f"EVAL_ERROR at {ts.date()} — a crash "
                                            "is neither a hit nor a miss"}
                    break
                if result is None:
                    continue
                fire_date = ts.strftime("%Y-%m-%d")
                # Diagnostic tier, never the pass bar: did it fire at HIS
                # geometry? A fire whose LPS re-anchored to the tighter inner
                # box IS a fire at that shelf — his rails may be the inner
                # pair, so both framings are consulted. The fired rails ride
                # along so a near-miss (a rail 0.18 box-heights off) stays
                # distinguishable from a different base without a re-run.
                on_parent = rails_match(
                    mark["resistance"], mark["support"],
                    result["_R"], result["_S"],
                    tol_box_frac=DEFAULT_RAIL_TOL_BOX_FRAC)
                inner_r, inner_s = result.get("_inner_R"), result.get("_inner_S")
                on_inner = (bool(result.get("_lps_in_inner"))
                            and inner_r is not None and inner_s is not None
                            and rails_match(mark["resistance"], mark["support"],
                                            inner_r, inner_s,
                                            tol_box_frac=DEFAULT_RAIL_TOL_BOX_FRAC))
                frag = {
                    "fired": agreement.fired_inside_window(
                        fire_date, mark.get("knowable_from_date"),
                        mark["as_of_date"]),
                    "fired_window": window,
                    "fire_date": fire_date,
                    "fire_tier": result.get("Tier"),
                    "fire_score": result.get("Score"),
                    "fire_R": float(result["_R"]),
                    "fire_S": float(result["_S"]),
                    "fire_lps_in_inner": bool(result.get("_lps_in_inner")),
                    "fire_rails_within_tol": bool(on_parent or on_inner),
                }
                if inner_r is not None and inner_s is not None:
                    frag["fire_inner_R"] = float(inner_r)
                    frag["fire_inner_S"] = float(inner_s)
                # Policy v2: rail/span agreement graded AT the fire session,
                # from the read the engine produced on THAT session's frame —
                # never the as-of snapshot (no clairvoyant grading). Purely
                # additive diagnostics; a canned result without box dates
                # simply omits the span figure.
                try:
                    frag["fire_rail_distances"] = agreement.rail_distances(
                        mark["resistance"], mark["support"],
                        frag["fire_R"], frag["fire_S"])
                except (ValueError, TypeError):
                    pass
                gate_margin = _binding_gate_margin(result)
                if gate_margin is not None:
                    frag["fire_gate_margin"] = gate_margin
                fire_box_start = result.get("_phase_b_start_date")
                if fire_box_start:
                    frag["fire_box_start_date"] = str(fire_box_start)
                    try:
                        frag["fire_span_overlap"] = round(agreement.span_overlap(
                            mark["box_start_date"], mark["box_end_date"],
                            str(fire_box_start), fire_date), 4)
                    except (ValueError, TypeError):
                        pass
                break
        # Move 4: a walked-but-silent window must say WHICH sessions the
        # universe prep refused (SKYT was refused 5/6 sessions, invisibly).
        # Computed only on the no-fire branch — the pass path pays nothing —
        # and flag-independent (universe gates are not engine flags), so ONE
        # scan (cached across the variant loop) serves every variant.
        # Inert evidence: report-only.
        if frag.get("fired") is False:
            if refusals is None:
                refusals = replay.refusal_scan(frozen, sessions)
            if refusals:
                frag["prep_refusals"] = _refusal_fragment(refusals, len(sessions))
        if clamp_note:
            frag["fired_window_clamped"] = clamp_note
        fragments.append(frag)
    return fragments

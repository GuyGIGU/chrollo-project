"""Grading one calibration mark against the reader: the fired walk.

The ONE implementation behind both the harness
(``python -m tools.calibration.calibration_harness --fired``) and the ledger's
Engine chip (``domains.calibration.fired``), so a chip can never drift from the
harness's report. It left the harness for this production home on 2026-09-24,
so the backend no longer imports ``tools/``.

``fired_one`` replays a BOX mark through the FULL nightly pipeline (the door's
``evaluate_ticker`` — the marks-corpus gate's exact decision) over the mark's
fair window, answering the operator's actual satisfaction bar: would this pick
have popped up on the screener in real trading time? Deep ``knowable_from``
walks are clamped to the frame's faithful-basis zone (the clamp is named in the
fragment) so a thin-basis no-fire can never pose as an assessed miss.

The election grade (``grade_one``: the old engine's box election snapped back
over a few sessions and judged against the drawn rails) retired with the old
engine (retire-old-engine, Phase 2b); the fired walk is the one grade.

Read-only by construction: frames load through the digest-resolved frame store
(frozen-or-refuse, never a vendor fetch) and flag overrides self-restore. This
module loads pandas and the engine at import, so backend code imports it inside
the function that needs it — the FastAPI boot stays engine-free.
"""
from __future__ import annotations

from collections import Counter
from contextlib import nullcontext

import pandas as pd

from core.calibration import agreement, replay
# The rail tolerance + matcher live with the agreement taxonomy (one home for
# "do these rails agree"); never import them from the engine here.
from core.calibration.agreement import DEFAULT_RAIL_TOL_BOX_FRAC, rails_match


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


# ---------------------------------------------------------------- fired (v2)
# The pops-up-live criterion (operator doctrine 2026-07-11): his bar is the
# ticker appearing in the nightly screener output, so the walk runs the FULL
# eval chain — not just a box read. Opt-in in the harness (--fired) because a
# full eval costs ~1s/session; the walk is bounded and the report stamps the
# bound.
# The fired-policy window is OWNED by the replay seam (one policy, every
# instrument — the marks-corpus ratchet grades the same criterion since the
# Guided List graduation 2026-07-24): re-exported here only for report
# stamping.
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
    """The Move-4 refusal-telemetry fragment — ONE shape for the report, so
    the printer can never read two spellings of the same evidence."""
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


def fired_one(mark: dict, variants: list[dict], *, frame_loader=None,
              evaluate=None) -> list:
    """One BOX mark through the FULL pipeline, per variant (harness v2).

    Non-box marks return None fragments: a negative asserts a no-read at ONE
    session and has no box to fire — window-hunting sessions to convict a
    negative would bias it.

    Returns one fragment per variant: ``fired`` True/False/None(unassessable)
    plus diagnostics. Sessions whose frozen lead-in cannot reproduce the live
    daily-structure basis are clamped OUT of the walk and the clamp named in
    the fragment; inside that faithful zone the pipeline's own floors decide
    — the walk never second-guesses the eval. A variant is a dict of settings
    overrides held for its walk (``replay.flag_capture``); the baseline ``{}``
    touches nothing.
    """
    if mark["verdict"] != "box":
        return [None for _ in variants]

    from webapp.backend import frame_store
    from engine_alpha.gate import EVAL_ERROR

    if evaluate is None:
        from engine_alpha.gate import evaluate_ticker as _evaluate_ticker

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
        with (replay.flag_capture(**variant) if variant else nullcontext()):
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
                # geometry? The fired rails ride along so a near-miss (a rail
                # 0.18 box-heights off) stays distinguishable from a different
                # base without a re-run.
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
                    "fire_rails_within_tol": bool(rails_match(
                        mark["resistance"], mark["support"],
                        result["_R"], result["_S"],
                        tol_box_frac=DEFAULT_RAIL_TOL_BOX_FRAC)),
                }
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

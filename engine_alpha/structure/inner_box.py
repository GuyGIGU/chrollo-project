"""The inner-box family: the Phase-D nested range, one scale down.

An inner box is a tighter range born INSIDE a validated parent Phase-B box —
the inner instance of the outer BC->AR anchoring (climax -> reaction -> range),
direction-agnostic because an inner base can sit inside a flat outer box.
``select_inner_box`` is the single selection rule shared by the live reader
(``bricks.find_inner_box``) and the diagnostic detector
(``consolidation.detect_boxes``); the election/validation primitives it runs on
stay in ``box_primitives`` (the dependency is strictly one-way).

Split out of ``box_primitives`` 2026-07-18 (Purity task 8) as a pure
structural move — every function verbatim.
"""
from __future__ import annotations

import math

from config import settings
from engine_alpha.structure.box_primitives import (
    EMPTY_BOX,
    _candidate_atr,
    _rebase_selected_candidate,
    collect_zigzag_candidates,
)
from engine_alpha.structure.pivots import _find_pivots, _pivot_order, _swing_skeleton

__all__ = [
    "inner_box_at",
    "detect_inner_root_swing",
    "mini_consolidation_position",
    "select_inner_box",
    "inner_zigzag",
    "RULED_POSITION_VALUES",
    "_detect_inner_phase_b_start",
]

# The position tolerance moved to settings.MINI_POSITION_TOL_ATR + the frozen
# manifest (ONE-Event-Map Task 12, 2026-08-30; value = the RULED 0.5, set at
# the 2026-08-30 rail-area seam). Read lazily below (AP-3/AP-10).

# The ONE declaration of the ruled closed set (EC-19/EC-33; council review
# 2026-08-30, Leach): the producer, the stamping-point assertion, the archive
# CHECK's test, and the tag rules all describe THIS tuple. A vocabulary change
# is an operator ruling + a deliberate edit here — never a drifted copy.
RULED_POSITION_VALUES = ("at_ceiling", "mid_range", "on_support", "touching_both")


def mini_consolidation_position(inner_r, inner_s, parent_r, parent_s, atr_val):
    """The mini-consolidation's POSITION against its parent's rails.

    Operator ruling 2026-08-23 (decisions.md story-chain row): the ceiling
    shelf and the inner mini-consolidation are ONE event, one mechanism —
    "no need to give it a new name just acknowledge its position which if the
    mini consolidation is found at the top that's a slightly higher quality."
    This is that acknowledgment: a pure measured attribute, no points, no
    gating (measure-first; the quality nuance is graded later, if ever).

    Closed set: ``"at_ceiling"`` / ``"mid_range"`` / ``"on_support"`` /
    ``"touching_both"`` — RULED the position vocabulary 2026-08-29/30
    (rails-are-areas: three values, not five) + the touching-both ruling
    2026-08-30. Serialized to ``setup_archive.inner_position`` (+ the raw
    signed distances) since the ONE-Event-Map Task-10 seam; display labels
    operator-signed 2026-08-30 (wireVocabulary.js POSITION_LABELS).

    Stated conventions (never implicit): the tolerance is
    ``MINI_POSITION_TOL_ATR`` candidate-ATRs; band comparisons are inclusive
    (a rail-touching tie lands IN the band); a structure satisfying BOTH bands
    reads ``touching_both`` — operator ruling 2026-08-30: differentiate a base
    that genuinely holds tight in the upper vicinity from one where the read
    is an artifact of the consolidation being about a bar's worth of height
    ("consider it as they were touching both") — its position carries no
    separating information, so it gets its own honest name, never a fabricated
    ceiling read (this replaced the ceiling-first tiebreak the same day it was
    documented). Returns None when any input is unusable (refused, never
    fabricated).
    """
    vals = (inner_r, inner_s, parent_r, parent_s, atr_val)
    if any(v is None for v in vals):
        return None
    if not all(math.isfinite(float(v)) for v in vals) or float(atr_val) <= 0:
        return None
    tol = settings.MINI_POSITION_TOL_ATR * float(atr_val)
    at_r = float(inner_r) >= float(parent_r) - tol
    at_s = float(inner_s) <= float(parent_s) + tol
    if at_r and at_s:
        return "touching_both"
    if at_r:
        return "at_ceiling"
    if at_s:
        return "on_support"
    return "mid_range"


def inner_zigzag(eval_df, start_idx, base_length):
    """Inner-stage zigzag detector scored over each candidate's own bar range.

    The inner path deliberately does NOT share the outer ATR snapshot — it
    reads its own window's volatility (`_candidate_atr` over the inner
    slice), the same yardstick its candidates are judged with."""
    eq_df = eval_df.iloc[start_idx:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        return EMPTY_BOX

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows)
    valid_candidates = collect_zigzag_candidates(
        eq_df, atr_val, min_candidate_days=settings.INNER_MIN_DAYS,
    )
    if not valid_candidates:
        return EMPTY_BOX

    selected = max(valid_candidates, key=lambda x: x[0])
    return _rebase_selected_candidate(selected, base_length)


def inner_box_at(eval_df, start, n, source="midpoint", root=None):
    """Run the inner-stage zigzag from ``start`` and normalize to an inner-box dict.

    Returns None when the window is too short or no valid inner box forms. The
    returned ``start_bar`` is df-positional (n - effective base length), matching
    the engine's ``phase_b_start = len(df) - base_len`` convention.
    """
    # inner_zigzag itself requires the search window to be >= MIN_BASE_DAYS, so
    # gate on that same (eval_df-relative) floor - INNER_MIN_DAYS is only the min
    # inner CANDIDATE length, not the window floor.
    if start >= len(eval_df) or (len(eval_df) - start) < settings.MIN_BASE_DAYS:
        return None
    r = inner_zigzag(eval_df, start, n - start)
    if r[0] == 0:
        return None
    eff_base_len, R, S, bw, rt, st = r[0], r[1], r[2], r[3], r[4], r[5]
    box = {
        "R": float(R), "S": float(S), "box_width": float(bw),
        "base_len": int(eff_base_len), "start_bar": int(n - eff_base_len),
        "r_touches": int(rt), "s_touches": int(st),
        "r_anchor_bar": int(r[7]), "s_anchor_bar": int(r[8]),
        "source": source,
        "search_start_bar": int(start),
        "climax_bar": None,
        "reaction_bar": None,
        "reaction_pct": None,
        "reaction_bars": None,
    }
    if root is not None:
        box.update({
            "climax_bar": int(root["bc_bar"]),
            "reaction_bar": int(root["ar_bar"]),
            "reaction_pct": float(root["reaction_pct"]),
            "reaction_bars": int(root["reaction_bars"]),
        })
    return box


def detect_inner_root_swing(eq_df):
    """Measure the inner climax -> reaction swing inside an outer base.

    Bars are offsets into ``eq_df``. This is the richer measurement behind
    ``_detect_inner_phase_b_start``; it reports the inner climax, the reaction
    low that can birth an inner range, and the reaction magnitude.
    """
    n = len(eq_df)
    if n < settings.INNER_MIN_DAYS + 2:
        return None

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values
    peaks_idx, valleys_idx, zigzag = _swing_skeleton(
        eq_highs, eq_lows, _pivot_order(n), _find_pivots)
    if not peaks_idx or not valleys_idx:
        return None
    if len(zigzag) < 2:
        return None

    # Most-recent qualifying inner climax: scan peak->valley limbs newest-first.
    for i in range(len(zigzag) - 2, -1, -1):
        zi, zj = zigzag[i], zigzag[i + 1]
        if zi[1] != 'peak' or zj[1] != 'valley':
            continue
        peak_p, val_p = zi[2], zj[2]
        if peak_p <= 0 or val_p >= peak_p:
            continue
        if (peak_p - val_p) / peak_p < settings.AR_MIN_DROP_PCT:
            continue
        ar_bar = int(zj[0])
        if (n - ar_bar) >= settings.INNER_MIN_DAYS:
            bc_bar = int(zi[0])
            return {
                "bc_bar": bc_bar,
                "ar_bar": ar_bar,
                "reaction_pct": round(float((peak_p - val_p) / peak_p), 4),
                "reaction_bars": int(ar_bar - bc_bar),
            }
    return None


def select_inner_box(eval_df, parent_pbs, base_len, bw_outer, n,
                     parent_r=None, parent_s=None):
    """Select the tighter Phase-D inner box nested in a parent range.

    Builds the inner-box start candidates (the mechanical midpoint + the detected
    inner climax), validates each via ``inner_box_at``, and returns the TIGHTEST
    that clears the ``INNER_TIGHTNESS_RATIO`` gate (None when no meaningfully-tighter
    inner exists). Shared by the live reader (``bricks.find_inner_box``) and the
    diagnostic detector (``consolidation.detect_boxes``) so the inner-selection rule
    lives in one place; returns the raw inner-box dict from ``inner_box_at`` and each
    caller adapts it (a dataclass for the reader, the dict for diagnostics).

    With the parent's rails given, the winner is stamped with its measured
    ``position`` (``mini_consolidation_position`` — the 2026-08-23 unification
    ruling's attribute) at this ONE point, on both consumer paths identically.
    The tolerance ATR is derived here from the parent window via the same
    ``_candidate_atr`` the election itself uses — never a caller-supplied ATR,
    so the live reader and the diagnostic mirror can never band differently.
    """
    midpoint_start = parent_pbs + int(base_len * settings.INNER_SEARCH_FRACTION)
    starts = {
        midpoint_start: {"source": "midpoint", "root": None},
    }
    root = detect_inner_root_swing(eval_df.iloc[parent_pbs:])
    if root is not None:
        root_abs = {
            "bc_bar": parent_pbs + int(root["bc_bar"]),
            "ar_bar": parent_pbs + int(root["ar_bar"]),
            "reaction_pct": root["reaction_pct"],
            "reaction_bars": root["reaction_bars"],
        }
        starts[root_abs["ar_bar"]] = {"source": "inner_climax", "root": root_abs}

    candidates = []
    for s, meta in starts.items():
        box = inner_box_at(
            eval_df, s, n,
            source=meta["source"], root=meta["root"],
        )
        if box is not None and box["box_width"] < bw_outer * settings.INNER_TIGHTNESS_RATIO:
            candidates.append(box)
    if not candidates:
        return None
    winner = min(candidates, key=lambda b: b["box_width"])
    if parent_r is not None and parent_s is not None:
        parent_win = eval_df.iloc[parent_pbs:]
        atr_val = _candidate_atr(parent_win, parent_win['High'].values,
                                 parent_win['Low'].values)
        winner["position"] = mini_consolidation_position(
            winner["R"], winner["S"], parent_r, parent_s, atr_val)
        # EC-19 leg 2 (write-time assertion at the single stamping point, the
        # _pool_label shape): the live DB's ADD COLUMN path cannot carry the
        # CHECK, so an out-of-vocabulary label must die HERE, loudly.
        if winner["position"] is not None and winner["position"] not in RULED_POSITION_VALUES:
            raise ValueError(
                f"inner position {winner['position']!r} is outside the ruled "
                f"closed set {RULED_POSITION_VALUES}")
        # The RAW signed distances ride beside the band (McKinney, PLAN Task 6):
        # the band is re-rulable offline against archived rows only if the
        # scalar it was banded from is recorded with it. Same refusal law as
        # the band — no position, no distances, never a fabricated number.
        if winner["position"] is not None:
            winner["position_distances"] = {
                "r_atr": (float(winner["R"]) - float(parent_r)) / float(atr_val),
                "s_atr": (float(winner["S"]) - float(parent_s)) / float(atr_val),
            }
        else:
            winner["position_distances"] = None
    else:
        winner["position"] = None
        winner["position_distances"] = None
    return winner


def _detect_inner_phase_b_start(eq_df):
    """Locate the inner Phase B start from a detected inner climax.

    The inner instance of the outer BC->AR anchoring, one scale down and
    direction-agnostic (an inner base can sit inside a flat outer box, so there
    is no 'dominant trend' to lean on). Within the outer-base window ``eq_df`` it
    scans zigzag peak->valley limbs from the most RECENT end backward and returns
    the first that is a genuine reaction: a drop >= AR_MIN_DROP_PCT (the same
    'what counts as a reaction' threshold the outer climax uses) whose reaction
    low still leaves >= settings.INNER_MIN_DAYS bars for an inner base to form. That low is
    the inner AR — the root swing the inner R/S is born from.

    Returns the inner AR-low bar as a 0-based OFFSET into ``eq_df``, or None when
    no clean inner climax exists (the caller falls back to its own heuristic).
    Pure measurement — reads price only, reuses existing tunables, decides nothing
    about scoring or eligibility.
    """
    root = detect_inner_root_swing(eq_df)
    return root["ar_bar"] if root is not None else None

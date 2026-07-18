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
    "select_inner_box",
    "inner_zigzag",
    "_detect_inner_phase_b_start",
]


def inner_zigzag(eval_df, start_idx, base_length, atr_override=None):
    """Inner-stage zigzag detector scored over each candidate's own bar range."""
    eq_df = eval_df.iloc[start_idx:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        return EMPTY_BOX

    eq_highs = eq_df['High'].values
    eq_lows = eq_df['Low'].values

    atr_val = _candidate_atr(eq_df, eq_highs, eq_lows, atr_override)
    valid_candidates = collect_zigzag_candidates(
        eq_df, base_length, atr_val, min_candidate_days=settings.INNER_MIN_DAYS,
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


def select_inner_box(eval_df, parent_pbs, base_len, bw_outer, n):
    """Select the tighter Phase-D inner box nested in a parent range.

    Builds the inner-box start candidates (the mechanical midpoint + the detected
    inner climax), validates each via ``inner_box_at``, and returns the TIGHTEST
    that clears the ``INNER_TIGHTNESS_RATIO`` gate (None when no meaningfully-tighter
    inner exists). Shared by the live reader (``bricks.find_inner_box``) and the
    diagnostic detector (``consolidation.detect_boxes``) so the inner-selection rule
    lives in one place; returns the raw inner-box dict from ``inner_box_at`` and each
    caller adapts it (a dataclass for the reader, the dict for diagnostics).
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
    return min(candidates, key=lambda b: b["box_width"]) if candidates else None


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

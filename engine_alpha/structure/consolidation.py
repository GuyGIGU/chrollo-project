"""
Wyckoff consolidation detection — identifies structural equilibrium bases
following macro trend exhaustion using zigzag-based S/R anchoring.

Diagnostic standalone detectors, composed from
``engine_alpha.structure.box_primitives``. The live screener does not call this module;
it reads structure chronologically via ``engine_alpha.structure.read_structure`` ->
``bricks``. What remains here serves diagnostic tools and public compatibility.

  ``detect_boxes(df)`` — parent+inner detector. Finds the outer BC→AR box as the
  base of record, then probes for a tighter nested Phase D range and returns both.

  ``find_outer_box(df)`` — anchor-enumeration only (no inner refinement).
  Used by diagnostics that need the parent candidate landscape directly.

Terminology (kept distinct on purpose):
  * BC / SC / AR  — Phase A, the TREND. The Buying/Selling Climax that ends the
    trend and the Automatic Rally/Reaction that first counters it. These mark
    where to BEGIN looking for a range; they are not the range's rails.
  * Resistance anchor / Support anchor — Phase B, the RANGE. The swing high/low
    levels the consolidation actually oscillates between. They MAY coincide with
    BC/AR but usually sit later/tighter (the support anchor climbs off a one-time
    AR low until the band is genuinely worked). Inner bases use mini-anchors.

Phase B procedure (the user's "is this a real trading range?" test):
  1. From the trend end (BC/AR), build a zigzag of alternating pivots.
  2. Propose Resistance/Support-anchor pairs from the zigzag limbs.
  3. For each pair ask: does price RESPECT, TOUCH, and ZIGZAG THROUGH both rails
     CONSTANTLY, with no dead space? (boundary respect + worked-equilibrium
     validity in box_primitives._validate_base_quality). Constant two-sided
     touch + no dead space is what makes a sparse / lopsided framing fail.
  4. Keep the EARLIEST pair that satisfies every constraint — "earliest of the
     ones that qualify" (longest cause among genuinely worked ranges). The
     dead-space gate makes the over-wide BC->AR framing invalid, so the anchors
     settle on the real equilibrium rather than the extremes.
  5. If NO pair qualifies anywhere -> reject the stock (no box).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.box_primitives import (
    collect_root_anchors,
    phase_b_zigzag,
)
from engine_alpha.structure.inner_box import select_inner_box


# Hierarchical-detection tunables (inner sub-box gating) live in settings and are
# read lazily at the use sites below — never cached at import time. This keeps the
# module importable under a different top-level ``config`` (e.g. the backend's
# broker config, when cwd is webapp/backend) without requiring the screener
# settings to be resolvable at import. See settings.INNER_TIGHTNESS_RATIO (inner
# must be >=25% tighter than parent) and settings.INNER_SEARCH_FRACTION (inner
# search begins at this fraction of the outer base).

# ---------------------------------------------------------------------------
# Public: outer-box anchor-enumeration (no inner refinement)
# ---------------------------------------------------------------------------

def find_outer_box(df: "pd.DataFrame", min_days: int | None = None,
                   select: str = "earliest") -> tuple:
    """Extreme-anchored consolidation detection (BC or SC).

    Anchor qualification (a bar `i` is a candidate anchor if):
      - BC: highs[i] is the max over the last LOCAL_PEAK_BARS bars AND the
            stock rose >= TREND_MIN_GAIN_PCT from a prior low within the
            last PRIOR_LOOKBACK bars, over >= MIN_MOVE_BARS. Validated by an
            Automatic Reaction (>= AR_MIN_DROP_PCT drop within AR_MAX_BARS).
            Phase B starts at the AR *low* (skips the descent).
      - SC: lows[i] is the min over the last LOCAL_PEAK_BARS bars AND fell
            >= TREND_MIN_GAIN_PCT from a prior high. Validated by a bounce
            (>= AR_MIN_DROP_PCT rise within AR_MAX_BARS). Phase B starts at
            the bounce *high* (skips the ascent).

    Every qualifying anchor is tried oldest-first; the FIRST whose Phase B
    yields a valid worked-equilibrium box wins (earliest cause). A BC/AR whose
    Phase B is sparse or full of dead space no longer validates, so the search
    falls through to a later anchor whose range is genuinely worked. If no anchor
    yields a valid box, the function returns EMPTY — the stock is rejected.

    Macro gate: stock must be in a bullish context (above SMA200 OR has a
    qualifying markup run somewhere in the window).

    Returns a 12-tuple:
        (base_length, R, S, box_width, r_touches, s_touches, breach_days,
         r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar,
         is_inner)
    is_inner is always False here (this function never refines to an inner
    sub-box). The hierarchical detector ``detect_boxes`` sets it True
    when a Phase D inner range replaces the outer box. All zeros on failure.
    """
    if min_days is None:
        min_days = settings.MIN_BASE_DAYS
    # 12-tuple: original 9 fields + bc_anchor_bar + phase_b_start_bar (both
    # df-positional) + is_inner (always False from this function).
    # eval_df = df.iloc[:-5] so eval_df-positional indices for [0..len(eval_df)-1]
    # align with df-positional indices in the same range.
    EMPTY = (0, 0, 0, 1.0, 0, 0, 0, 0, 0, 0, 0, False)

    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    if len(eval_df) < min_days + 15:
        return EMPTY

    # Engine-aligned ATR snapshot — same bar (df[-6] == eval_df[-1]) used
    # downstream for LPS zone tolerance, so Phase B and the LPS detector
    # share one volatility frame.
    if 'ATR_10' in eval_df.columns:
        atr_snapshot = float(eval_df['ATR_10'].iloc[-1])
        if np.isnan(atr_snapshot) or atr_snapshot <= 0:
            atr_snapshot = None
    else:
        atr_snapshot = None

    anchors = collect_root_anchors(eval_df, min_days)
    if not anchors:
        return EMPTY

    # --- PHASE B: pick the EARLIEST anchor whose Phase B passes quality gates ---
    # `anchors` is built most-recent-first (line above scans range(scan_hi, scan_lo-1, -1)),
    # so reversed() gives oldest-first. phase_b_zigzag already enforces all
    # quality checks (box width, boundary respect, touch density, midline crosses);
    # any non-EMPTY return is a valid Phase B. Preferring the earliest valid anchor
    # maximizes Wyckoff "cause" (base age) and resists the truncation failure where
    # a mid-base upthrust is selected over the true climax because its shorter
    # window mechanically yields a tighter box.
    for _atype, _abar, phase_b_start, _R, _S in reversed(anchors):
        base_length = len(df) - phase_b_start
        if select == "debug":
            # Diagnostic: return the candidate landscape for the first anchor
            # that yields a valid Phase B (the one the live engine would use).
            probe = phase_b_zigzag(
                eval_df, phase_b_start, base_length, atr_override=atr_snapshot,
                select="best",
            )
            if probe[0] != 0:
                return phase_b_zigzag(
                    eval_df, phase_b_start, base_length,
                    atr_override=atr_snapshot, select="debug",
                )
            continue
        result = phase_b_zigzag(
            eval_df, phase_b_start, base_length, atr_override=atr_snapshot,
            select=select,
        )
        if result[0] != 0:
            # Effective phase_b_start = original AR-low anchor + the
            # cand_start offset baked into result[0]. Mirrors the
            # downstream computation `phase_b_start = len(df) - base_len`.
            effective_phase_b_start = len(df) - result[0]
            return result + (_abar, effective_phase_b_start, False)

    return [] if select == "debug" else EMPTY


# ---------------------------------------------------------------------------
# Parent + Inner: the nested range model (draw both) — see docs/structure_legend.md
# ---------------------------------------------------------------------------

def detect_boxes(df, min_days=None, select="earliest"):
    """Parent (outer) box + the best-of-both inner companion.

    The **parent** is the base of record (always == ``find_outer_box``). The
    **inner** is the tighter Phase D range: the BETTER (tighter) of the inner
    found from the mechanical midpoint and the inner found from the
    detected inner climax (``_detect_inner_phase_b_start``), keeping only one that
    clears the same ``settings.INNER_TIGHTNESS_RATIO`` (0.75) gate. None when no
    meaningfully-tighter inner exists.

    Pure measurement: it composes the two boxes but decides nothing about firing
    or scoring — the caller applies the model (parent = base, inner = nested
    Phase D range).

    Returns ``{"parent": <12-tuple>, "inner": <dict|None>}``.
    """
    if min_days is None:
        min_days = settings.MIN_BASE_DAYS

    parent = find_outer_box(df, min_days=min_days, select=select)
    if parent[0] == 0:
        return {"parent": parent, "inner": None}

    base_len, bw_outer, parent_pbs = parent[0], parent[3], parent[10]
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    if parent_pbs >= len(eval_df):
        return {"parent": parent, "inner": None}

    n = len(df)
    inner = select_inner_box(eval_df, parent_pbs, base_len, bw_outer, n)
    return {"parent": parent, "inner": inner}

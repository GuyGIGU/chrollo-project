"""Chronological Wyckoff structure bricks.

Pure typed adapters over the calibrated structure detectors. These functions do
not score, mutate inputs, or invent thresholds; they answer whether one
structural brick fits at the supplied point in the left-to-right reader.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.phase_features import _phase_c_candidate
from engine_alpha.structure.box_primitives import (
    ELECTED_POOLS,
    backext_shared_rail,
    collect_root_anchors,
    collect_zigzag_candidates,
    select_phase_b_candidate,
)
from engine_alpha.structure.inner_box import select_inner_box
from engine_alpha.structure.lps import detect_lps, lps_range_threshold
from engine_alpha.structure.market_structure import first_reaction_after
from engine_alpha.structure.metrics import measure_equilibrium
from engine_alpha.structure.segmentation import segment_swings


_SEG_LEAD_IN = 60
_SEG_AR_TOL = 10
# Inner sub-box tunables (the INNER_* settings) are read lazily at the use
# sites, never cached at import time — see core/structure/consolidation.py.


@dataclass
class RootSwing:
    kind: str
    climax_bar: int
    ar_bar: int
    R: float
    S: float
    reaction_pct: float
    reaction_bars: int


@dataclass
class EquilibriumBox:
    S: float
    R: float
    start_bar: int
    base_len: int
    box_width: float
    quality: float
    r_touches: int
    s_touches: int
    breach_days: int
    r_anchor_bar: int
    s_anchor_bar: int
    n_full_traversals: int
    traversal_density: float
    # The full measure_equilibrium dict for THIS box, measured once at election;
    # evaluation consumes it instead of re-measuring the same window/rails/ATR.
    equilibrium: Optional[dict] = None
    # The electing pool's closed-set provenance (strict / rescued / band /
    # story) — Event Map program Task 11: a rescued cohort must stay
    # separable in the archive, the harness output, and forward-returns
    # cohorts, forever. A story election also carries the admitting sentence
    # (the evidence the pool judged — the substrate read at the elected
    # geometry is a DIFFERENT basis and may legally disagree).
    elected_pool: str = "strict"
    story_admission_profile: "Optional[str]" = None


@dataclass
class InnerBox:
    S: float
    R: float
    start_bar: int
    base_len: int
    box_width: float
    r_touches: int
    s_touches: int
    r_anchor_bar: int
    s_anchor_bar: int
    source: str
    search_start_bar: int        # where the inner search began (diagnostic; archived)
    climax_bar: Optional[int]
    reaction_bar: Optional[int]
    reaction_pct: Optional[float]
    reaction_bars: Optional[int]
    # The full select_inner_box dict for THIS box (anchors box-relative), stored
    # at election; evaluation consumes it instead of a field-by-field inverse map.
    detection: Optional[dict] = None


@dataclass
class Spring:
    tip_bar: int
    recovery_bar: int
    undercut_atr: float
    recovery_bars: int
    time_loc: float
    spring_vol_z: Optional[float]
    event_date: Optional[str]
    spring_type: str = "SPRING"
    # The full _phase_c_candidate dict for THIS spring (the bin_c shape), stored
    # at election; measure_phases consumes it instead of a field-by-field inverse map.
    detection: Optional[dict] = None


@dataclass
class Lps:
    low_bar: int
    start_bar: int
    end_bar: int
    zone_type: str
    trigger: float
    length: int
    offset: int
    setup_type: str
    low: float
    high: float
    vol_contraction: float
    tightness_ratio: float
    descent_frac: float
    high_descent_frac: float
    window_range_pct_box: float
    high_extension_box: float
    high_extension_atr: float
    profile_unit: float
    profile_unit_pct: float
    pullback_profile: float
    terminal_low_tolerance: float
    spread_expansion_profile: float
    first_high: float
    last_low: float
    window_high: float
    window_low: float
    swing_type: str = "terminal_valley"
    lps_anchor_bar: Optional[int] = None
    lps_anchor_date: Optional[str] = None
    lps_low_bar: Optional[int] = None
    lps_low_date: Optional[str] = None
    lps_swing_depth_pct: Optional[float] = None
    lps_swing_depth_atr: Optional[float] = None
    lps_swing_depth_box: Optional[float] = None
    # The full detect_lps result dict for THIS LPS, stored at election;
    # evaluation consumes it instead of a field-by-field inverse map.
    detection: Optional[dict] = None


def _finite(x) -> bool:
    try:
        return x is not None and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def find_root_swing(
    df: "pd.DataFrame",
    search_from_bar: int = 0,
    atr=None,
) -> RootSwing | None:
    """Find the next calibrated climax -> automatic-reaction root swing."""
    if df is None or not ({"High", "Low", "Close"} <= set(df.columns)):
        return None

    start = max(0, int(search_from_bar))
    # Frame parity with ``find_outer_box``: anchors AND the Phase-B box are found
    # on ``df[:-5]``, reserving the last 5 bars as the live trigger/edge zone (a
    # late breakout there must not perturb the consolidation's pivots). eval_df
    # positions align with df over the scanned range, so the returned bars are
    # valid full-df indices; the LPS/spring bricks still read the full df.
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    anchors = collect_root_anchors(eval_df, settings.MIN_BASE_DAYS)
    for kind, climax_bar, ar_bar, R, S in reversed(anchors):
        if climax_bar < start:
            continue
        denom = R if kind == "BC" else S
        reaction_pct = (R - S) / denom if denom > 0 else 0.0
        return RootSwing(
            kind=kind,
            climax_bar=int(climax_bar),
            ar_bar=int(ar_bar),
            R=float(R),
            S=float(S),
            reaction_pct=round(float(reaction_pct), 4),
            reaction_bars=int(ar_bar - climax_bar),
        )
    return None


def _rebase_pair_trace(trace, from_idx, offset):
    """Shift pair-cascade bars recorded window-relative into df positions."""
    if trace is None:
        return
    for rec in trace[from_idx:]:
        rec["r_anchor_bar"] += offset
        rec["s_anchor_bar"] += offset
        rec["cand_start"] += offset


def _pool_label(value) -> str:
    """The single stamping point of the archive's electing-pool provenance.
    The column is a CLOSED set: a future rung that mislabels (or leaves the
    Candidate slot unset) must fail HERE, loudly — a blind str() would
    happily persist "None" and silently fork the rescued cohort forever."""
    label = str(value)
    if label not in ELECTED_POOLS:
        raise ValueError(
            f"unknown electing-pool label {value!r} — the archive's closed "
            f"set is {'/'.join(ELECTED_POOLS)}")
    return label


def validate_equilibrium(
    df: "pd.DataFrame",
    root: RootSwing,
    atr,
    trace=None,
) -> EquilibriumBox | None:
    """Validate a worked Phase-B range born from ``root``.

    ``trace``: optional list; when given, the pair election narrates itself —
    every candidate R/S pair examined is recorded with its verdict (rejection
    gate, or "elected" for the winner), bars df-positional. ``None`` (the live
    default) records nothing and changes nothing. When the flag-gated
    shared-rail back-extension moves the elected start, the elected record
    carries ``backext_bars`` and says so in its detail.
    """
    if df is None or root is None or not _finite(atr) or float(atr) <= 0:
        return None
    if not ({"High", "Low", "Close"} <= set(df.columns)):
        return None
    if root.ar_bar < 0 or root.ar_bar >= len(df):
        return None

    # Same df[:-5] frame the anchor was found on (see find_root_swing): the box
    # is the consolidation as of ~5 bars ago, not contaminated by the live edge.
    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    if root.ar_bar >= len(eval_df):
        return None
    eq_df = eval_df.iloc[root.ar_bar:]
    if len(eq_df) < settings.MIN_BASE_DAYS:
        return None

    # Scope the cascade to THIS call: collect + the traversal gate match records
    # inside the list they are handed, so a caller-reused list must never leak
    # earlier calls' records into their view. Appended back at the end.
    cascade = [] if trace is not None else None
    candidates = collect_zigzag_candidates(
        eq_df,
        len(df) - root.ar_bar,   # base_length in full-df terms (matches legacy)
        float(atr),
        enforce_traversal=True,
        trace=cascade,
    )
    if not candidates:
        if trace is not None:
            _rebase_pair_trace(cascade, 0, root.ar_bar)
            trace.extend(cascade)
        return None

    selected = select_phase_b_candidate(candidates, "earliest")
    # Trailing *_ absorbs the judged-window length (slot 10); this path rebases
    # the anchors itself against root.ar_bar below, so it reads the raw candidate.
    quality, R, S, box_width, r_touches, s_touches, breach_days, \
        r_anchor, s_anchor, cand_start, *_ = selected

    # Shared-rail back-extension (unconditional since the 2026-07-18 fold):
    # candidate starts are pinned to their anchor pair, so the earliest-valid
    # election cannot reach an earlier start its own gates would bless (gap #3, AGCO).
    # Walk the ELECTED start left to the earliest rail-touching pivot with a
    # band-conforming span; rails and the election itself are untouched.
    ext_start = backext_shared_rail(eq_df, float(R), float(S), int(cand_start),
                                    float(atr))

    if trace is not None:
        key = (int(r_anchor), int(s_anchor), int(cand_start))
        n_valid = 0
        winner = None
        for rec in cascade:
            if rec["verdict"] != "valid":
                continue
            n_valid += 1
            if (rec["r_anchor_bar"], rec["s_anchor_bar"], rec["cand_start"]) == key:
                winner = rec
        if winner is not None:
            winner["verdict"] = "elected"
            winner["stage"] = "selection"
            winner["detail"] = "earliest-of-valid (longest cause)" + (
                f"; beat {n_valid - 1} later valid framing(s)" if n_valid > 1 else "")
            if ext_start != cand_start:
                winner["backext_bars"] = int(cand_start - ext_start)
                winner["detail"] += (
                    f"; start back-extended {int(cand_start - ext_start)} bar(s) "
                    "to a shared-rail pivot (BOX_BACKEXT)")
        _rebase_pair_trace(cascade, 0, root.ar_bar)
        trace.extend(cascade)

    start_bar = int(root.ar_bar + ext_start)
    base_len = int(len(df) - start_bar)
    box_df = df.iloc[start_bar:]
    equilibrium = measure_equilibrium(box_df, float(R), float(S), float(atr))
    n_swings = int(equilibrium["n_swings"])
    n_full = int(equilibrium["n_full_traversals"])
    density = n_full / n_swings if n_swings > 0 else 0.0

    return EquilibriumBox(
        S=float(S),
        R=float(R),
        start_bar=start_bar,
        base_len=base_len,
        box_width=float(box_width),
        quality=float(quality),
        r_touches=int(r_touches),
        s_touches=int(s_touches),
        breach_days=int(breach_days),
        r_anchor_bar=int(root.ar_bar + r_anchor),
        s_anchor_bar=int(root.ar_bar + s_anchor),
        n_full_traversals=n_full,
        traversal_density=float(density),
        equilibrium=equilibrium,
        elected_pool=_pool_label(selected[11]),
        story_admission_profile=(str(selected[12])
                                 if selected[12] is not None else None),
    )


def find_inner_box(
    df: "pd.DataFrame",
    box: EquilibriumBox,
    atr,
) -> InnerBox | None:
    """The tighter Phase-D mini-consolidation nested in the parent box."""
    if df is None or box is None or not _finite(atr) or float(atr) <= 0:
        return None
    if not ({"High", "Low", "Close"} <= set(df.columns)):
        return None

    skip = settings.STRUCTURE_EDGE_SKIP_BARS
    eval_df = df.iloc[:-skip] if len(df) > skip else df
    parent_pbs = box.start_bar
    if parent_pbs >= len(eval_df):
        return None

    n = len(df)
    selected = select_inner_box(eval_df, parent_pbs, box.base_len, box.box_width, n)
    if selected is None:
        return None
    start_bar = int(selected["start_bar"])
    return InnerBox(
        S=float(selected["S"]),
        R=float(selected["R"]),
        start_bar=start_bar,
        base_len=int(selected["base_len"]),
        box_width=float(selected["box_width"]),
        r_touches=int(selected["r_touches"]),
        s_touches=int(selected["s_touches"]),
        r_anchor_bar=start_bar + int(selected["r_anchor_bar"]),
        s_anchor_bar=start_bar + int(selected["s_anchor_bar"]),
        source=selected["source"],
        search_start_bar=int(selected["search_start_bar"]),
        climax_bar=selected["climax_bar"],
        reaction_bar=selected["reaction_bar"],
        reaction_pct=selected["reaction_pct"],
        reaction_bars=selected["reaction_bars"],
        detection=selected,
    )


def find_spring(
    df: "pd.DataFrame",
    box: EquilibriumBox,
    atr,
) -> Spring | None:
    """Find an optional calibrated Phase-C spring inside ``box``."""
    if df is None or box is None or not _finite(atr) or float(atr) <= 0:
        return None
    if box.base_len <= 0 or box.start_bar < 0 or box.start_bar >= len(df):
        return None

    base_seg = df.iloc[box.start_bar:]
    result = _phase_c_candidate(
        df,
        base_seg,
        box_start=box.start_bar,
        base_len=box.base_len,
        R=box.R,
        S=box.S,
        atr_val=float(atr),
    )
    if not result.get("bin_c_present"):
        return None

    return Spring(
        tip_bar=int(result["bin_c_event_bar"]),
        recovery_bar=int(result["bin_c_recovery_bar"]),
        undercut_atr=float(result["bin_c_undercut_atr"]),
        recovery_bars=int(result["bin_c_recovery_bars"]),
        time_loc=float(result["bin_c_time_loc"]),
        spring_vol_z=result["bin_c_spring_vol_z"],
        event_date=result["bin_c_event_date"],
        spring_type=result["bin_c_type"],
        detection=result,
    )


def find_lps(
    df: "pd.DataFrame",
    box: EquilibriumBox,
    atr,
    *,
    diagnose: bool = False,
):
    """Find the calibrated Phase-D LPS that completes the structure.

    With ``diagnose=True`` returns ``(lps_or_None, rejects)`` — the detector's
    reject counter — so the narrative trace can report WHY no LPS completed.
    Without it, returns ``lps_or_None`` (unchanged signature for the live path).
    """
    def _out(lps, rejects=None):
        return (lps, rejects) if diagnose else lps

    if df is None or box is None or len(df) == 0:
        return _out(None)
    if not _finite(atr) or float(atr) <= 0:
        return _out(None)
    required = {"High", "Low", "Close", "Volume", "Vol_50"}
    if not (required <= set(df.columns)):
        return _out(None)
    if box.base_len <= 0 or box.start_bar < 0 or box.start_bar >= len(df):
        return _out(None)

    work_df = df
    if "Spread" not in work_df.columns:
        work_df = work_df.assign(Spread=work_df["High"] - work_df["Low"])

    base_df = work_df.iloc[box.start_bar:]
    if base_df.empty:
        return _out(None)

    base_range_threshold = lps_range_threshold(base_df, atr)
    swing_complete_idx = max(int(box.r_anchor_bar), int(box.s_anchor_bar))
    detected = detect_lps(
        work_df,
        work_df.iloc[-1],
        box.S,
        box.R,
        float(atr),
        base_range_threshold,
        box.base_len,
        swing_complete_idx,
        diagnose=diagnose,
    )
    result, rejects = detected if diagnose else (detected, None)
    if not result:
        return _out(None, rejects)

    start = int(result["start_index"])
    end = int(result["end_index"])
    lps = Lps(
        low_bar=int(result["low_index"]),
        start_bar=start,
        end_bar=end,
        zone_type=result["zone_type"],
        trigger=float(result["trigger_price"]),
        length=int(result["length"]),
        offset=int(result["offset"]),
        setup_type=result["setup_type"],
        low=float(result["low"]),
        high=float(result["high"]),
        vol_contraction=float(result["vol_contraction"]),
        tightness_ratio=float(result["tightness_ratio"]),
        descent_frac=float(result["descent_frac"]),
        high_descent_frac=float(result["high_descent_frac"]),
        window_range_pct_box=float(result["window_range_pct_box"]),
        high_extension_box=float(result["high_extension_box"]),
        high_extension_atr=float(result["high_extension_atr"]),
        profile_unit=float(result["profile_unit"]),
        profile_unit_pct=float(result["profile_unit_pct"]),
        pullback_profile=float(result["pullback_profile"]),
        terminal_low_tolerance=float(result["terminal_low_tolerance"]),
        spread_expansion_profile=float(result["spread_expansion_profile"]),
        first_high=float(result["first_high"]),
        last_low=float(result["last_low"]),
        window_high=float(result["window_high"]),
        window_low=float(result["window_low"]),
        swing_type=result.get("swing_type", "terminal_valley"),
        lps_anchor_bar=(int(result["lps_anchor_bar"])
                        if result.get("lps_anchor_bar") is not None else None),
        lps_anchor_date=result.get("lps_anchor_date"),
        lps_low_bar=(int(result["lps_low_bar"])
                     if result.get("lps_low_bar") is not None else None),
        lps_low_date=result.get("lps_low_date"),
        lps_swing_depth_pct=result.get("lps_swing_depth_pct"),
        lps_swing_depth_atr=result.get("lps_swing_depth_atr"),
        lps_swing_depth_box=result.get("lps_swing_depth_box"),
        detection=result,
    )
    return _out(lps, rejects)


def _enforce_bc_downswing(df, root, box, climax_bar, ar_bar):
    """Keep a Buying-Climax overlay a genuine high -> reaction-low (DOWN) swing.

    A BC root *is* a high topping into its reaction, so the painted climax must
    sit ABOVE the AR. When the resolved anchor is an UP swing instead (the climax
    sits below the AR -- a stale low-altitude BC climax wired to a box-level
    reaction, e.g. XMTR climax@48.7 -> AR@82.1), relocate the climax to the
    prominent run-up high in the lead-in before the box so the overlay reads the
    way the operator's eye does.

    SC roots (a selling-climax low -> rally high, a legitimately UP overlay) and
    every genuine down-swing are left untouched: root.kind is partly a stale scan
    origin (see tools.structure_case_audit / the emergent-box note), so only the
    unambiguous BC-up contradiction is repaired. Overlay-only -> shadow-safe.
    """
    if getattr(root, "kind", None) != "BC":
        return climax_bar, ar_bar
    highs = df["High"].values
    n = len(df)
    if not (0 <= climax_bar < n and 0 <= ar_bar < n):
        return climax_bar, ar_bar
    if float(highs[ar_bar]) <= float(highs[climax_bar]):
        return climax_bar, ar_bar          # already a high -> (lower) reaction
    pbs = int(box.start_bar)
    lo = max(0, pbs - _SEG_LEAD_IN)
    window = highs[lo:pbs]
    if not len(window):
        return climax_bar, ar_bar
    return lo + int(np.argmax(window)), pbs


def _enforce_climax_terminality(df, root, box, climax_bar, ar_bar, atr):
    """Reject a resolved climax the trend visibly out-ran before the box.

    The trend model defines the climax as the trend's EXTREME pivot, and the
    macro bridge already enforces exactly this (its "climax terminality"
    True-Root rule). The calibrated bridge/seed fallback paths had no such
    check, so a stale scan-origin pause could paint as Phase A while price ran
    far past it into the box — FLXS drew climax 04-28 -> AR 05-19 and then
    rallied +38.5% into the 06-26 box open (the seed + AR_MAX_BARS synthetic
    offset, fleet-measured: 59% of setups continued >5% past their claimed
    climax).

    Test (mirror-symmetric): between the claimed climax and the box open,
    price may exceed the climax by at most PHASE_A_CLIMAX_TERMINALITY_EXCESS
    x the bridge height (ATR floor guards a degenerate height) — the same
    constant semantics as PIP_MACRO_MAX_POST_EXCESS. A violating pair
    re-anchors to the box's own run-up (the prominent extreme of the
    _SEG_LEAD_IN window -> the box open) — the local synthesis the
    ancient-origin fallback already uses. The repair window INCLUDES the
    box-open bar: when the box opens ON the extreme the pair collapses to
    the sanctioned one-bar boundary form (climax == AR == box open, operator
    ruling 2026-07-20), which makes the repair terminal by construction —
    the doctrine gate caught 27 setups leaking past a pbs-exclusive window.

    Unknown root kinds pass through untouched (no direction to test). Overlay
    + Phase-A diagnostics only (bars_since_BC / descent_length / bin_a — the
    engine_config_version rotation partitions the archive seam): no rail,
    gate, score, or tier reads these anchors.
    """
    kind = getattr(root, "kind", None)
    if kind not in ("BC", "SC"):
        return climax_bar, ar_bar
    n = len(df)
    pbs = int(box.start_bar)
    if not (0 <= climax_bar < n and 0 <= ar_bar < n and 0 < pbs < n):
        return climax_bar, ar_bar
    if climax_bar + 1 > pbs:
        return climax_bar, ar_bar
    highs = df["High"].values
    lows = df["Low"].values
    atr_floor = float(atr) if (_finite(atr) and float(atr) > 0) else 0.0
    excess = settings.PHASE_A_CLIMAX_TERMINALITY_EXCESS
    lo = max(0, pbs - _SEG_LEAD_IN)
    if kind == "BC":
        height = max(float(highs[climax_bar]) - float(lows[ar_bar]), atr_floor)
        span = highs[climax_bar + 1:pbs + 1]
        if not len(span) or float(np.max(span)) <= float(highs[climax_bar]) + excess * height:
            return climax_bar, ar_bar
        window = highs[lo:pbs + 1]
        if not len(window):
            return climax_bar, ar_bar
        return lo + int(np.argmax(window)), pbs
    height = max(float(highs[ar_bar]) - float(lows[climax_bar]), atr_floor)
    span = lows[climax_bar + 1:pbs + 1]
    if not len(span) or float(np.min(span)) >= float(lows[climax_bar]) - excess * height:
        return climax_bar, ar_bar
    window = lows[lo:pbs + 1]
    if not len(window):
        return climax_bar, ar_bar
    return lo + int(np.argmin(window)), pbs


def _first_impulse_ar_end(df, climax_bar, ar_bar, atr):
    """Tighten the overlay AR to the trend model's FIRST reaction off the climax.

    Operator model (2026-07-05): the automatic reaction is the first CONTINUOUS
    counter-move after the trend's TERMINAL swing (the climax) -- read from the
    HH/HL trend model, not a raw fixed-bar retrace. The reaction runs to the low
    that anchors the base: significance is measured against the trend's FULL leg
    (the whole advance the climax ended), and it is closed only at the first BIG
    confirmed bounce off that low -- not a mid-decline pause (which over-tightened
    the earlier terminal-sub-leg + stall read) and not the eventual base-edge low
    the raw resolver can drag past (a later second leg down). Mirror-symmetric
    across BC and SC roots.

    This is a thin overlay adapter: the read lives in
    ``market_structure.first_reaction_after`` (structure measures); here we only
    enforce the drawn-overlay contract. Overlay-only and TIGHTEN-ONLY: the search
    is bounded to the drawn span ``[climax_bar, ar_bar]`` and can only move the AR
    EARLIER, so the chronological invariant ``climax_bar <= ar_bar <=
    phase_b_start_bar`` is preserved by construction. Returns a bar in
    ``(climax_bar, ar_bar]``, or ``ar_bar`` unchanged when no clean first reaction
    resolves inside the span (a genuinely one-way descent that only stops at the
    base edge). No-op with the flag off, so both states are byte-identical on the
    scoring/tier/canonical-shadow surface. NOTE: a flip is NOT byte-identical on
    the ARCHIVED ``bin_a_*`` columns (``ar_bar`` feeds ``measure_phases`` →
    ``writer``, read by ``analyze``); no freeze gate covers that seam, so a live
    flip needs a ``bin_a_*`` guard / ``engine_config_version`` partition first.
    """
    if not settings.AR_FIRST_REACTION_ENABLED:
        return ar_bar
    if not _finite(atr) or float(atr) <= 0:
        return ar_bar
    n = len(df)
    if not (0 <= climax_bar < ar_bar < n):
        return ar_bar

    # Direction from the drawn swing (post BC-down enforcement): a buying-climax
    # tops into a lower reaction (+1); a selling-climax troughs into a higher
    # one (-1).
    highs = df["High"].values
    direction = 1 if float(highs[climax_bar]) >= float(highs[ar_bar]) else -1
    reaction_bar = first_reaction_after(
        df, climax_bar,
        direction=direction,
        atr=float(atr),
        retrace_frac=float(settings.AR_RETRACE_FRAC),
        up_leg_lookback=int(settings.AR_UP_LEG_LOOKBACK),
        bounce_atr_mult=float(settings.AR_BOUNCE_ATR_MULT),
        bounce_drop_frac=float(settings.AR_BOUNCE_DROP_FRAC),
        end_bar=int(ar_bar),
    )
    if reaction_bar is not None and climax_bar < reaction_bar <= ar_bar:
        return int(reaction_bar)
    return ar_bar


def resolve_phase_a(
    df: "pd.DataFrame",
    root: RootSwing,
    box: EquilibriumBox,
    atr,
) -> tuple[int, int]:
    """Return the local Phase-A root swing for an already-validated box.

    Resolves the raw anchor, enforces the BC-down invariant so a buying climax
    never paints as an up-swing (see _enforce_bc_downswing), enforces climax
    terminality so a mid-trend pause never paints as the trend end (see
    _enforce_climax_terminality), then tightens the AR to the first impulsive
    reaction so the overlay stops dragging to the base edge (see
    _first_impulse_ar_end; flag-gated, no-op when off)."""
    climax_bar, ar_bar = _resolve_phase_a_raw(df, root, box, atr)
    climax_bar, ar_bar = _enforce_bc_downswing(df, root, box, climax_bar, ar_bar)
    climax_bar, ar_bar = _enforce_climax_terminality(df, root, box, climax_bar, ar_bar, atr)
    ar_bar = _first_impulse_ar_end(df, climax_bar, ar_bar, atr)
    return climax_bar, ar_bar


def _resolve_phase_a_raw(
    df: "pd.DataFrame",
    root: RootSwing,
    box: EquilibriumBox,
    atr,
) -> tuple[int, int]:
    """The unguarded resolution: bridge -> segmentation root -> local fallbacks."""
    phase_b_start_bar = box.start_bar
    base_len = box.base_len
    bc_anchor_bar = root.climax_bar
    phase_b_start = len(df) - base_len
    # bridge_* constraints: the macro Phase-A read (flag-gated) must tell THIS
    # box's story — its AR may not land beyond the box birth (Phase A ends where
    # Phase B opens: the chronological invariant ar_bar <= phase_b_start_bar),
    # its climax type must match the canonical root kind, and its AR must
    # reach the box's level (a story floating above R / below S is a breakout
    # or other-leg tale) — else it abstains and the calibrated order-N read
    # speaks. No-op with the flag off (bridge_end_max is read only by the macro
    # branch). A macro bridge whose AR overruns the box start paints Phase A
    # INSIDE the box (the LUV class) — the merge contract abstains on it.
    _lvl_tol = settings.TOUCH_TOLERANCE_ATR * atr
    seg = segment_swings(df, atr, lookback=base_len + _SEG_LEAD_IN,
                         bridge_end_max=phase_b_start_bar,
                         bridge_kind=getattr(root, "kind", None),
                         bridge_ar_price_max=float(box.R) + _lvl_tol,
                         bridge_ar_price_min=float(box.S) - _lvl_tol)

    dom = seg.get("dominant_direction", 0)
    bridge = None
    if dom != 0:
        for swing in seg.get("swings", []):
            # The AR must not overrun the box open: an asymmetric window (up to
            # _SEG_AR_TOL bars BEFORE box start, never after) keeps the read
            # inside the chronological invariant ar_bar <= phase_b_start_bar.
            # (Was a symmetric abs() tolerance that could return an AR up to
            # _SEG_AR_TOL bars INSIDE the box — Phase A painted inside Phase B.)
            if (swing["direction"] == -dom
                    and phase_b_start_bar - _SEG_AR_TOL <= swing["end_bar"] <= phase_b_start_bar
                    and phase_b_start_bar - _SEG_LEAD_IN <= swing["start_bar"] < phase_b_start_bar):
                if bridge is None or swing["abs_disp_atr"] > bridge["abs_disp_atr"]:
                    bridge = swing
    if bridge is not None:
        return bridge["start_bar"], bridge["end_bar"]

    root_sw = seg.get("root_swing")
    if root_sw is not None:
        try:
            root_start = int(root_sw["bc_bar"])
            root_end = int(root_sw["ar_bar"])
        except (KeyError, TypeError, ValueError):
            root_start = root_end = None
        if root_start is not None and root_start < root_end < len(df):
            if root_end <= phase_b_start_bar:
                return root_start, root_end

    # Final fallback. The seed root can be an ancient SCAN ORIGIN: the box is
    # emergent from candidate enumeration, so the *same* box is reached from roots
    # hundreds of bars earlier (see tools.structure_case_audit). Returning that
    # seed climax would paint a stale Phase A — a 2024 climax on a 2026 box — when
    # the bridge/segmentation searches above find nothing local. When the seed
    # sits beyond the local bridge window, synthesize the climax -> AR from the
    # box's own run-up (the prominent high feeding the reaction the box opens on)
    # so the overlay anchor stays local; within the window, keep the raw anchor.
    if phase_b_start_bar - bc_anchor_bar > _SEG_LEAD_IN:
        lo = max(0, phase_b_start_bar - _SEG_LEAD_IN)
        run_up_highs = df["High"].values[lo:phase_b_start_bar]
        local_climax_bar = (
            lo + int(np.argmax(run_up_highs)) if len(run_up_highs) else phase_b_start_bar
        )
        return local_climax_bar, phase_b_start_bar

    phase_a_end_bar = min(
        phase_b_start_bar,
        bc_anchor_bar + settings.AR_MAX_BARS,
    )
    return bc_anchor_bar, phase_a_end_bar


# ---------------------------------------------------------------------------
# The cause-before-effect precondition (measure-only)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CauseVerdict:
    """Whether a matured Phase-A cause precedes an elected box.

    A pure MEASUREMENT — no gate, no score, mutates nothing. ``read_structure``
    turns ``matured`` into the veto decision; the trace/audit reads the
    sub-signals to explain WHY a name was (not) vetoed. Composed from three
    already-existing reads (two top-down + the shelf's own tightness), never a
    new detector:

      * ``bridge_validated`` — the box-INDEPENDENT macro bridge found a terminal
        climax->AR that survived its terminality/floor/oscillation guards in the
        lead-in (``macro_bridge_zigzag`` returned a story, not ``[]``). This is
        the recall-SAFE operand: a matured base validates here even when it sits
        far above R (a deep throwback), while MIDD's live up-leg abstains. It is
        NOT the box-CONSTRAINED resolver fallback, which abstains for the benign
        "the AR doesn't reach THESE rails" reason and would over-veto matured
        bases whose climax was re-anchored.
      * ``pre_box_trend`` / ``box_trend`` — the HH/HL staircase trend state on
        each side of the box open (``read_swing_map``). A live up-staircase
        through the rails reads ``'up'`` / ``'up'``.
      * ``lps_tightness_ratio`` — the elected LPS's final shelf-candle spread
        over the base profile unit (``lps.tightness_ratio``, a structural fact).
        The third leg: MIDD's shelf never tightened (ratio 0.957, the census
        minimum) while every seeded winner tightened more — so a box is causeless
        only if its final shelf is ALSO loose (ratio > ``CAUSE_LPS_LOOSE_MAX``).

    ``matured`` is False (cause absent -> veto candidate) ONLY when all three
    agree: the bridge abstained AND both trend states read a live up-staircase
    AND the LPS shelf is loose. This is an AND-narrowing — a tighter gate than
    the bridge+staircase pair alone, so it can only ever rescue a winner the two
    would have dropped, never drop a new one (the seeded tight-shelf winners
    BP/LECO/MEOH/NTCT/VLO clear it). Every other path — a validated bridge, a
    non-'up' trend state, a tight shelf, a degenerate frame/box, a bad ATR,
    a missing LPS — returns ``matured=True``. Fail-OPEN is the law: a veto on the
    mere absence of a positive cause-absent signal would drop a winner, and
    recall is the pass/fail gate.
    """
    matured: bool
    bridge_validated: bool
    pre_box_trend: str
    box_trend: str
    lps_tightness_ratio: float


def cause_maturity(df, box, atr, lps=None) -> CauseVerdict:
    """Does a matured Phase-A cause precede this elected box? (measure-only.)

    The MIDD class: a box drawn over a live trend that never matured a cause —
    price trends up THROUGH both rails into a blow-off, so the consolidation
    predates its own climax. This reads the two top-down signals that ALREADY
    exist and reports whether the cause matured; it draws nothing, gates
    nothing, mutates nothing. ``read_structure`` owns the veto decision.

    Operand A (box-INDEPENDENT, the recall-safe primary): over the SAME lead-in
    + box window ``resolve_phase_a`` reads (``base_len + _SEG_LEAD_IN``), does
    the macro bridge validate ANY terminal climax->AR? ``macro_bridge_zigzag``
    returns ``[]`` on abstention (a trend still making highs, a reaction that
    never held, a leg glued across other structure) — exactly the MIDD tell —
    and a >=2-pivot story otherwise. A validated story is a matured cause, full
    stop: return early and never even compute the trend state (the O(n) swing
    walk runs only when the cause is already in doubt — Performance's
    short-circuit).

    Operand B (consulted ONLY on abstention): the HH/HL staircase trend state on
    each side of the box open (``read_swing_map``). A live up-staircase reads
    ``pre_box == 'up'`` AND ``box == 'up'`` — the box floating up through its own
    rails rather than a two-sided range.

    Operand C (the shelf tell): the elected ``lps.tightness_ratio`` — the last
    shelf candle's spread over the base profile unit. MIDD's shelf never tightened
    (0.957, the census minimum); every seeded winner's did (nearest 0.842). A box
    is causeless only if its final shelf is ALSO loose (ratio > ``CAUSE_LPS_LOOSE_MAX``).

    ``matured=False`` (veto candidate) requires ALL THREE operands to agree the
    cause is absent: the bridge abstained AND the staircase is a live up-run AND
    the shelf is loose. The shelf leg is an AND-narrowing — it can only rescue a
    winner the bridge+staircase pair would have vetoed (the seeded tight-shelf
    names), never drop a new one. Every other path returns ``matured=True``.

    Replay-honest: a pure function of ``df`` up to the election bar plus the
    elected box. ``macro_bridge_zigzag`` treats the right edge as an unconfirmed
    'now' (never an AR), so the eval-at-T verdict equals the live verdict at T.
    """
    from engine_alpha.structure.phase_a import macro_bridge_zigzag

    # Operand A — the box-independent macro bridge over the same window
    # resolve_phase_a reads. Abstention ([]) is the primary cause-absent signal.
    try:
        n = len(df)
        lookback = int(getattr(box, "base_len", 0)) + _SEG_LEAD_IN
        lo = max(0, n - lookback) if lookback > 0 else 0
        highs = df["High"].values[lo:]
        lows = df["Low"].values[lo:]
        story = macro_bridge_zigzag(highs, lows, k_max=settings.PIP_MACRO_K_MAX)
        bridge_validated = len(story) >= 2
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        # Fail OPEN on ANY error in the frame setup OR the bridge itself — a
        # degenerate frame (the common case) or an unexpected fault both leave
        # the cause unproven, and refusing to veto can only keep a name, never
        # drop a winner (recall is the gate). The catch is deliberately broad.
        return CauseVerdict(matured=True, bridge_validated=False,
                            pre_box_trend="", box_trend="", lps_tightness_ratio=0.0)

    if bridge_validated:
        # A matured cause validated in the lead-in — never veto. The trend-state
        # read (Operand B) is not even computed (short-circuit).
        return CauseVerdict(matured=True, bridge_validated=True,
                            pre_box_trend="", box_trend="", lps_tightness_ratio=0.0)

    # Operand B — only on abstention: is the box a live up-staircase?
    from engine_alpha.structure.event_map import read_swing_map

    tape = read_swing_map(df, box, atr)
    pre_trend = tape["pre_box"]["trend_state"]
    box_trend = tape["box"]["trend_state"]
    live_up_run = (pre_trend == "up" and box_trend == "up")

    # Operand C — the shelf tell: does the elected LPS's final candle stay loose?
    # Fail-open on a missing/NaN ratio (reads 0.0 -> not loose -> never vetoes).
    raw_tr = getattr(lps, "tightness_ratio", None)
    lps_tr = float(raw_tr) if _finite(raw_tr) else 0.0
    loose_lps = lps_tr > settings.CAUSE_LPS_LOOSE_MAX

    matured = not (live_up_run and loose_lps)
    return CauseVerdict(matured=matured, bridge_validated=False,
                        pre_box_trend=pre_trend, box_trend=box_trend,
                        lps_tightness_ratio=lps_tr)

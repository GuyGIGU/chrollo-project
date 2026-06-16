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
from core.structure.bin_features import _phase_c_candidate
from core.structure.box_candidates import (
    _collect_zigzag_candidates,
    _detect_inner_root_swing,
    _select_phase_b_candidate,
)
from core.structure.consolidation import _collect_root_anchors, _inner_box_at
from core.structure.lps import detect_lps
from core.structure.metrics import measure_traversal
from core.structure.segmentation import segment_swings


_SEG_LEAD_IN = 60
_SEG_AR_TOL = 10
# Inner sub-box tunables are read lazily at the use sites (settings.INNER_*),
# never cached at import time — see the note in core/structure/consolidation.py.


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
    anchors = _collect_root_anchors(eval_df, settings.MIN_BASE_DAYS)
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


def validate_equilibrium(
    df: "pd.DataFrame",
    root: RootSwing,
    atr,
) -> EquilibriumBox | None:
    """Validate a worked Phase-B range born from ``root``."""
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

    candidates = _collect_zigzag_candidates(
        eq_df,
        len(df) - root.ar_bar,   # base_length in full-df terms (matches legacy)
        float(atr),
        enforce_traversal=True,
    )
    if not candidates:
        return None

    selected = _select_phase_b_candidate(candidates, "earliest")
    # Trailing *_ absorbs the judged-window length (slot 10); this path rebases
    # the anchors itself against root.ar_bar below, so it reads the raw candidate.
    quality, R, S, box_width, r_touches, s_touches, breach_days, \
        r_anchor, s_anchor, cand_start, *_ = selected

    start_bar = int(root.ar_bar + cand_start)
    base_len = int(len(df) - start_bar)
    box_df = df.iloc[start_bar:]
    traversal = measure_traversal(box_df, float(R), float(S), float(atr))
    n_swings = int(traversal["n_swings"])
    n_full = int(traversal["n_full_traversals"])
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
    bw_outer = box.box_width
    midpoint_start = parent_pbs + int(box.base_len * settings.INNER_SEARCH_FRACTION)
    starts = {
        midpoint_start: {"source": "midpoint", "root": None},
    }
    root = _detect_inner_root_swing(eval_df.iloc[parent_pbs:])
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
        inner = _inner_box_at(
            eval_df, s, n,
            source=meta["source"], root=meta["root"],
        )
        if inner is not None and inner["box_width"] < bw_outer * settings.INNER_TIGHTNESS_RATIO:
            candidates.append(inner)
    if not candidates:
        return None

    selected = min(candidates, key=lambda b: b["box_width"])
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
    )


def find_lps(
    df: "pd.DataFrame",
    box: EquilibriumBox,
    atr,
) -> Lps | None:
    """Find the calibrated Phase-D LPS that completes the structure."""
    if df is None or box is None or len(df) == 0:
        return None
    if not _finite(atr) or float(atr) <= 0:
        return None
    required = {"High", "Low", "Close", "Volume", "Vol_50"}
    if not (required <= set(df.columns)):
        return None
    if box.base_len <= 0 or box.start_bar < 0 or box.start_bar >= len(df):
        return None

    work_df = df
    if "Spread" not in work_df.columns:
        work_df = work_df.assign(Spread=work_df["High"] - work_df["Low"])

    base_df = work_df.iloc[box.start_bar:]
    if base_df.empty:
        return None

    base_range_threshold = max(
        float(base_df["Spread"].quantile(settings.LPS_RANGE_PERCENTILE)),
        1.2 * float(atr),
    )
    swing_complete_idx = max(int(box.r_anchor_bar), int(box.s_anchor_bar))
    result = detect_lps(
        work_df,
        work_df.iloc[-1],
        box.S,
        box.R,
        float(atr),
        base_range_threshold,
        box.base_len,
        swing_complete_idx,
    )
    if not result:
        return None

    start = int(result["start_index"])
    end = int(result["end_index"])
    return Lps(
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
    )


def resolve_phase_a(
    df: "pd.DataFrame",
    root: RootSwing,
    box: EquilibriumBox,
    atr,
) -> tuple[int, int]:
    """Return the local Phase-A root swing for an already-validated box."""
    phase_b_start_bar = box.start_bar
    base_len = box.base_len
    bc_anchor_bar = root.climax_bar
    phase_b_start = len(df) - base_len
    seg = segment_swings(df, atr, lookback=base_len + _SEG_LEAD_IN)

    dom = seg.get("dominant_direction", 0)
    bridge = None
    if dom != 0:
        for swing in seg.get("swings", []):
            if (swing["direction"] == -dom
                    and abs(swing["end_bar"] - phase_b_start_bar) <= _SEG_AR_TOL
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

    phase_a_end_bar = min(
        phase_b_start_bar,
        bc_anchor_bar + settings.AR_MAX_BARS,
    )
    return bc_anchor_bar, phase_a_end_bar

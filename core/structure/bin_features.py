"""
Bin features — "where am I in the base?" measurements.

A measure-only layer (see docs/structure_legend.md) that slices an
already-detected base into its named regions and reports raw descriptive
numbers per region. It detects NOTHING new and scores NOTHING: it consumes the
anchors the detector + LPS finder already produced (BC/AR, the box R/S, the
inner-box flag, the LPS window) and re-expresses them as per-region size,
range, and volume character, plus two cross-region comparisons and the
Last-Supper stretch.

The four regions (df-positional, all best-effort — any region that can't be
placed is emitted as ``None`` so young bases degrade gracefully):

    Bin A   — the climax event: BC/SC -> AR (the trend-exhaustion lead-in).
    Bin B   — the working base: the validated box itself (``base_df``).
    Bin D   — the right-most Phase D region. Boundary comes from the SAME rule the
              scoping overlay draws (``scope._resolve_phase_d_start``), so the
              drawn band and this measured bin can never drift apart. Tagged
              ``bin_d_boundary_source`` = "inner_box" (a real mini-consolidation)
              or "heuristic" (the final-third fallback).
    Bin LPS — the exact LPS candidate bars.

Last Supper (the over-extension axis from the legend): how far the LPS foot
sits ABOVE the box that birthed it — ``lps_stretch_atr`` (in ATR) and
``lps_stretch_box`` (in box-heights). Near-zero / negative = the LPS formed in
or below the box (no stretch); large positive = a stretched, Last-Supper-risk
LPS far from its energy source.

Phase-D support behavior: because the right side should often show demand
getting more aggressive, Bin D also measures its own ascending-support quality
and compares it with the full-base support quality.

PURE MEASUREMENT. No opinion, no gate, never imports the scoring or archive
layers. Returns un-prefixed keys; the pipeline maps them to ``_bin_*`` /
``_lps_*`` archive fields.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from core.structure.metrics import measure_support_slope
from core.structure.scope import _resolve_phase_d_start


def _empty() -> dict:
    return {
        "bin_a_bars": None,
        "bin_a_range_pct": None,
        "bin_a_volume_ratio": None,
        "bin_b_bars": None,
        "bin_b_range_pct": None,
        "bin_b_volume_ratio": None,
        # Bin B interior trajectory (the "eyes inside the base" fusion) — see
        # _cog_interior. All None on a young / degenerate base.
        "bin_b_cog_end": None,
        "bin_b_cog_crossings": None,
        "bin_b_cog_rng": None,
        "bin_b_cog_corr": None,
        "bin_c_present": False,
        "bin_c_type": None,
        "bin_c_event_date": None,
        "bin_c_undercut_atr": None,
        "bin_c_recovery_bars": None,
        "bin_c_time_loc": None,
        "bin_c_spring_vol_z": None,
        "bin_d_bars": None,
        "bin_d_range_pct": None,
        "bin_d_volume_ratio": None,
        "bin_d_support_slope_atr": None,
        "bin_d_higher_low_frac": None,
        "bin_d_ascending_support_quality": None,
        "bin_d_boundary_source": None,
        "bin_lps_bars": None,
        "lps_position_in_box": None,
        "bin_d_vs_b_range_ratio": None,
        "bin_d_vs_b_volume_ratio": None,
        "bin_d_vs_b_support_quality_delta": None,
        "lps_stretch_atr": None,
        "lps_stretch_box": None,
    }


def _finite(x) -> bool:
    try:
        return x is not None and np.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _round(x, nd: int = 4) -> Optional[float]:
    return round(float(x), nd) if _finite(x) else None


def _range_pct(seg: "pd.DataFrame") -> Optional[float]:
    """(max High - min Low) / min Low over the segment, as a fraction. None-safe."""
    if seg is None or seg.empty:
        return None
    try:
        lo = float(seg["Low"].min())
        hi = float(seg["High"].max())
    except (KeyError, ValueError, TypeError):
        return None
    if not (_finite(lo) and _finite(hi)) or lo <= 0:
        return None
    return _round((hi - lo) / lo)


def _mean_vol(seg: "pd.DataFrame") -> Optional[float]:
    if seg is None or seg.empty or "Volume" not in seg.columns:
        return None
    v = float(seg["Volume"].mean())
    return v if _finite(v) else None


def _cog_interior(seg: "pd.DataFrame", R: float, S: float) -> dict:
    """Interior trajectory of the box (Bin B): slice the base into adaptive
    time-columns and track the center-of-gravity — the mean close position in the
    box (0 = at S, 1 = at R) — across them. This is the "eyes inside the base"
    fusion with the vertical bin system: where price *sits* through the range over
    time, not just where the rails are.

    RESIDENCE measure -> Close-based by design (it answers "where did price
    settle", exactly like measure_equilibrium's dwell). It is deliberately NOT a
    High/Low reach measure — those (touches, boundary respect, spread) stay on
    High/Low elsewhere. Pure: no opinion, no gate.

    Returns (all None on a young / degenerate base, so it degrades gracefully):
        bin_b_cog_end        mean CoG of the last ~2 time-columns: where price
                             sits now (>~0.6 pressing R, <~0.35 testing S)
        bin_b_cog_crossings  how many times the CoG track crosses the box mid-line
                             (>=2 = a genuine two-sided / oscillating range;
                             0-1 = a one-way traverse)
        bin_b_cog_rng        max-min of the CoG track: how much of the box height
                             the center swept
        bin_b_cog_corr       corr of per-bar position vs time: trajectory direction
                             (+ climbing toward R, - sagging toward S)
    """
    out = {"bin_b_cog_end": None, "bin_b_cog_crossings": None,
           "bin_b_cog_rng": None, "bin_b_cog_corr": None}
    if seg is None or "Close" not in seg.columns:
        return out
    box = float(R - S) if (_finite(R) and _finite(S)) else 0.0
    if not (np.isfinite(box) and box > 0):
        return out
    closes = seg["Close"].values.astype(float)
    n = len(closes)
    if n < 8:
        return out
    pos = np.clip((closes - S) / box, 0.0, 1.0)
    ncols = int(np.clip(n // 5, 4, 8))
    cols = np.array_split(np.arange(n), ncols)
    cog = np.array([pos[c].mean() for c in cols if len(c)])
    if len(cog) < 3:
        return out

    side = np.sign(cog - 0.5)
    side = side[side != 0]
    crossings = int(np.sum(side[1:] != side[:-1])) if len(side) > 1 else 0
    corr = float(np.corrcoef(np.arange(n), pos)[0, 1]) if pos.std() > 1e-9 else 0.0
    if not np.isfinite(corr):
        corr = 0.0
    out["bin_b_cog_end"] = round(float(cog[-2:].mean()), 4)
    out["bin_b_cog_crossings"] = crossings
    out["bin_b_cog_rng"] = round(float(cog.max() - cog.min()), 4)
    out["bin_b_cog_corr"] = round(corr, 4)
    return out


def _date_at(df: "pd.DataFrame", idx: int) -> Optional[str]:
    if idx < 0 or idx >= len(df):
        return None
    try:
        return str(df.index[idx])[:10]
    except (IndexError, TypeError, ValueError):
        return None


def _support_test_tolerance(R: float, S: float, atr_val: float) -> float:
    """Above-S tolerance for held tests.

    Held tests should sit near support from above. Unlike the LPS undercut zone,
    do not floor this at half the box height: on tight boxes that would label
    ordinary lower-half chop as Phase C.
    """
    if not _finite(atr_val) or float(atr_val) <= 0:
        return 0.0
    return settings.BIN_C_HELD_TEST_ATR_MAX * float(atr_val)


def _volume_z(seg: "pd.DataFrame", base_seg: "pd.DataFrame") -> Optional[float]:
    if seg is None or seg.empty or base_seg is None or base_seg.empty:
        return None
    if "Volume" not in seg.columns or "Volume" not in base_seg.columns:
        return None
    try:
        base_mean = float(base_seg["Volume"].mean())
        base_std = float(base_seg["Volume"].std())
        if not (_finite(base_mean) and _finite(base_std)) or base_std <= 0:
            return None
        return _round((float(seg["Volume"].mean()) - base_mean) / base_std)
    except (KeyError, ValueError, TypeError):
        return None


def _phase_c_candidate(df: "pd.DataFrame", base_seg: "pd.DataFrame", *,
                       box_start: int, base_len: int, R: float, S: float,
                       atr_val: float) -> dict:
    """Measure the best late support test: spring first, held test otherwise."""
    empty = {
        "bin_c_present": False,
        "bin_c_type": None,
        "bin_c_event_date": None,
        "bin_c_undercut_atr": None,
        "bin_c_recovery_bars": None,
        "bin_c_time_loc": None,
        "bin_c_spring_vol_z": None,
    }
    if base_len <= 0 or not (_finite(S) and _finite(R)):
        return empty
    if not ({"Low", "Close"} <= set(df.columns)):
        return empty

    n = len(df)
    late_start = box_start + int(base_len * settings.BIN_C_LATE_BOX_FRACTION)
    late_start = max(box_start, min(late_start, n - 1))
    scan_end = n
    atr = float(atr_val) if _finite(atr_val) and float(atr_val) > 0 else None
    if atr is None:
        return empty
    min_undercut = settings.BIN_C_UNDERCUT_ATR_MIN * atr
    support_tol = _support_test_tolerance(R, S, atr_val)

    springs = []
    held_tests = []
    for idx in range(late_start, scan_end):
        try:
            low = float(df["Low"].iloc[idx])
            close = float(df["Close"].iloc[idx])
        except (KeyError, ValueError, TypeError):
            continue
        if not (_finite(low) and _finite(close)):
            continue

        depth = float(S) - low
        if depth >= min_undercut and low < float(S):
            recovery_idx = None
            max_recovery_idx = min(n - 1, idx + settings.BIN_C_RECOVERY_BARS_MAX)
            for ridx in range(idx, max_recovery_idx + 1):
                if float(df["Close"].iloc[ridx]) >= float(S):
                    recovery_idx = ridx
                    break
            if recovery_idx is None:
                springs = []
                held_tests = []
                break
            springs.append({
                "idx": idx,
                "recovery_idx": recovery_idx,
                "undercut_atr": (depth / atr if atr is not None else None),
            })
            continue
        if low < float(S):
            continue
        elif low >= float(S) and low <= float(S) + support_tol and close >= float(S):
            held_tests.append({
                "idx": idx,
                "recovery_idx": idx,
                "undercut_atr": 0.0,
            })

    candidate_type = None
    candidate = None
    if springs:
        candidate_type = "SPRING"
        candidate = sorted(springs, key=lambda c: (c["idx"], c["undercut_atr"] or 0.0))[-1]
    elif held_tests:
        candidate_type = "HELD_TEST"
        candidate = held_tests[-1]
    if candidate is None:
        return empty

    idx = int(candidate["idx"])
    recovery_idx = int(candidate["recovery_idx"])
    denom = max(1, base_len - 1)
    event_seg = df.iloc[idx:recovery_idx + 1]
    return {
        "bin_c_present": True,
        "bin_c_type": candidate_type,
        "bin_c_event_date": _date_at(df, idx),
        "bin_c_undercut_atr": _round(candidate["undercut_atr"]),
        "bin_c_recovery_bars": int(recovery_idx - idx),
        "bin_c_time_loc": _round(np.clip((idx - box_start) / denom, 0.0, 1.0)),
        "bin_c_spring_vol_z": _volume_z(event_seg, base_seg),
    }


def measure_bins(
    df: "pd.DataFrame",
    *,
    bc_anchor_bar: Optional[int],
    phase_b_start_bar: Optional[int],
    base_len: int,
    is_inner_box: bool,
    lps_offset: int,
    lps_length: int,
    R: float,
    S: float,
    atr_val: float,
    phase_d_start_bar: Optional[int] = None,
    support_test_start_bar: Optional[int] = None,
    lps_R: Optional[float] = None,
    lps_S: Optional[float] = None,
) -> dict:
    """Measure the named regions of an already-detected base. Pure.

    Args:
        df: per-ticker OHLCV frame (needs High/Low/Volume). All emitted bar
            counts and slices are positional in THIS frame.
        bc_anchor_bar: df-positional BC/SC climax bar (Bin A start). In the live
            pipeline this is the (possibly swing-reconnected) anchor scope uses.
        phase_b_start_bar: df-positional equilibrium-body start (Bin A end / the
            AR low or bounce high).
        base_len: trimmed working-box length -> box start = len(df) - base_len.
        is_inner_box: True when the detector picked an inner sub-box (Phase D is
            then that box; boundary source = "inner_box").
        phase_d_start_bar: optional explicit Phase-D start. Used when the parent
            remains the base of record and an inner Phase D range is drawn inside
            it.
        lps_offset, lps_length: locate the LPS window — it ends at
            len(df) - lps_offset (exclusive) and spans lps_length bars.
        R, S: box ceiling / floor prices (for LPS position + stretch).
        atr_val: ATR snapshot used to normalize the Last-Supper stretch.
        support_test_start_bar: optional df-positional start of a measured
            right-side support-test cluster; used only to locate Bin D when no
            inner box exists.
        lps_R, lps_S: optional active LPS box ceiling/floor. Parent R/S still
            define Bin B/D; these only define LPS position/stretch when the LPS
            was elected against an inner range.

    Returns a JSON-safe dict of un-prefixed keys (see _empty for the shape).
    """
    out = _empty()
    n = len(df) if df is not None else 0
    if n == 0 or base_len <= 0:
        return out
    if not ({"High", "Low"} <= set(df.columns)):
        return out

    last = n - 1
    box_start = n - base_len

    # Volume baseline: trailing-50 mean (== Vol_50), computed here so the module
    # is self-contained and works on the seed path too (no Vol_50 column needed).
    vol_ref = None
    if "Volume" in df.columns:
        vr = float(df["Volume"].iloc[-min(50, n):].mean())
        vol_ref = vr if (_finite(vr) and vr > 0) else None

    has_atr = _finite(atr_val) and float(atr_val) > 0
    box_height = float(R - S) if (_finite(R) and _finite(S)) else None
    active_R = float(lps_R) if _finite(lps_R) else R
    active_S = float(lps_S) if _finite(lps_S) else S
    active_box_height = (
        float(active_R - active_S) if (_finite(active_R) and _finite(active_S)) else None
    )
    active_box_ok = active_box_height is not None and active_box_height > 0

    # ── LPS window (df-positional, clamped) ─────────────────────────────────
    lps_end = n - max(0, int(lps_offset))
    lps_start = max(0, lps_end - max(1, int(lps_length)))
    lps_end = min(lps_end, n)
    has_lps = lps_end > lps_start
    lps_low = None
    if has_lps:
        seg_lps = df.iloc[lps_start:lps_end]
        try:
            lps_low = float(seg_lps["Low"].min())
        except (KeyError, ValueError, TypeError):
            lps_low = None
        out["bin_lps_bars"] = int(lps_end - lps_start)

    # ── Bin A — climax event (BC/SC -> AR) ──────────────────────────────────
    a0 = bc_anchor_bar if (bc_anchor_bar is not None and 0 <= bc_anchor_bar < n) else None
    a1 = phase_b_start_bar if (phase_b_start_bar is not None and 0 < phase_b_start_bar <= n) else None
    if a0 is not None and a1 is not None and a0 < a1:
        seg_a = df.iloc[a0:a1]
        out["bin_a_bars"] = int(a1 - a0)
        out["bin_a_range_pct"] = _range_pct(seg_a)
        va = _mean_vol(seg_a)
        if va is not None and vol_ref:
            out["bin_a_volume_ratio"] = _round(va / vol_ref)

    # ── Bin B — the working base (the validated box) ────────────────────────
    seg_b = df.iloc[box_start:n]
    vb = _mean_vol(seg_b)
    out["bin_b_bars"] = int(base_len)
    out["bin_b_range_pct"] = _range_pct(seg_b)
    if vb is not None and vol_ref:
        out["bin_b_volume_ratio"] = _round(vb / vol_ref)
    support_b = measure_support_slope(seg_b, atr_val)
    # Interior trajectory of Bin B (the time x price "inside the base" read).
    out.update(_cog_interior(seg_b, R, S))
    out.update(_phase_c_candidate(
        df, seg_b, box_start=box_start, base_len=base_len,
        R=R, S=S, atr_val=atr_val,
    ))

    # ── Bin D — the right-most Phase D region (shared boundary rule) ────────
    b = phase_b_start_bar if (phase_b_start_bar is not None and 0 <= phase_b_start_bar < n) else None
    d = _resolve_phase_d_start(
        box_start=box_start, base_len=base_len, last=last,
        is_inner_box=is_inner_box, has_lps_window=has_lps,
        lps_start=lps_start, b=b, phase_d_start_bar=phase_d_start_bar,
        support_test_start_bar=support_test_start_bar,
    )
    vd = None
    if d is not None and d < n:
        seg_d = df.iloc[d:n]
        vd = _mean_vol(seg_d)
        out["bin_d_bars"] = int(n - d)
        out["bin_d_range_pct"] = _range_pct(seg_d)
        out["bin_d_boundary_source"] = (
            "inner_box" if (is_inner_box or phase_d_start_bar is not None)
            else "support_tests" if support_test_start_bar is not None
            else "heuristic"
        )
        if vd is not None and vol_ref:
            out["bin_d_volume_ratio"] = _round(vd / vol_ref)
        support_d = measure_support_slope(seg_d, atr_val)
        out["bin_d_support_slope_atr"] = support_d["slope_atr"]
        out["bin_d_higher_low_frac"] = support_d["higher_low_frac"]
        out["bin_d_ascending_support_quality"] = support_d["quality"]

    # ── D-vs-B comparisons (is Phase D tighter/quieter than Phase B?) ───────
    if out["bin_d_range_pct"] is not None and out["bin_b_range_pct"]:
        out["bin_d_vs_b_range_ratio"] = _round(out["bin_d_range_pct"] / out["bin_b_range_pct"])
    if vd is not None and vb:
        out["bin_d_vs_b_volume_ratio"] = _round(vd / vb)
    if out["bin_d_support_slope_atr"] is not None and support_b["slope_atr"] is not None:
        out["bin_d_vs_b_support_quality_delta"] = _round(
            out["bin_d_ascending_support_quality"] - support_b["quality"]
        )

    # ── LPS position in the box + Last-Supper stretch ───────────────────────
    if lps_low is not None and active_box_ok:
        out["lps_position_in_box"] = _round((lps_low - active_S) / active_box_height)
        # Stretch = how far the LPS foot sits ABOVE the box ceiling R (the energy
        # source). <=0 -> LPS in/below the box (no over-extension); large +ve ->
        # stretched far above = Last-Supper risk.
        out["lps_stretch_box"] = _round((lps_low - active_R) / active_box_height)
    if lps_low is not None and has_atr:
        out["lps_stretch_atr"] = _round((lps_low - active_R) / float(atr_val))

    return out

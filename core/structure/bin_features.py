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
              "spring" (true Phase-C spring recovery), "v_tip" (final recovered
              V-tip), "support_tests" (support-test cluster), or "heuristic"
              (the final-third fallback).
    Bin C   — an optional spring: a late, measured undercut of support that
              recovers by Close. Most bases do not have one.
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
        "bin_c_event_bar": None,
        "bin_c_undercut_atr": None,
        "bin_c_recovery_bars": None,
        "bin_c_recovery_bar": None,
        "bin_c_time_loc": None,
        "bin_c_spring_vol_z": None,
        "bin_d_bars": None,
        "bin_d_start_bar": None,
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
    """Measure the Phase-C spring: the TIP of a V that springs below support.

    A spring is not just any Low under S. It is the tip of a V — a real reaction
    DOWN into a meaningful undercut of support (the left arm), then a recovery UP
    that reclaims S by Close (the right arm). Three tests, in order, reject the
    shallow "tests at support" that are not springs (the small hiccups the eye
    dismisses):

      1. undercut floor  — the tip Low dips >= BIN_C_UNDERCUT_ATR_MIN below S
                           (and not deeper than the breakdown cap / box cap).
      2. V arms          — a real drop into the tip (left shoulder High - tip,
                           >= BIN_C_V_DROP_ATR_MIN) AND a real recovery out of it
                           (right shoulder High - tip, >= BIN_C_V_RECOVERY_ATR_MIN).
      3. reclaim         — Close back above S within BIN_C_RECOVERY_BARS_MAX.

    All thresholds are ATR-normalized. Most bases have no Phase C and that is
    normal. Pure measurement; never gates score/tier.
    """
    empty = {
        "bin_c_present": False,
        "bin_c_type": None,
        "bin_c_event_date": None,
        "bin_c_event_bar": None,
        "bin_c_undercut_atr": None,
        "bin_c_recovery_bars": None,
        "bin_c_recovery_bar": None,
        "bin_c_time_loc": None,
        "bin_c_spring_vol_z": None,
    }
    if base_len <= 0 or not (_finite(S) and _finite(R)):
        return empty
    if not ({"High", "Low", "Close"} <= set(df.columns)):
        return empty
    atr = float(atr_val) if (_finite(atr_val) and float(atr_val) > 0) else None
    if atr is None:
        return empty

    n = len(df)
    late_start = box_start + int(base_len * settings.BIN_C_LATE_BOX_FRACTION)
    late_start = max(box_start + 1, min(late_start, n - 1))
    min_undercut = settings.BIN_C_UNDERCUT_ATR_MIN * atr
    max_undercut = settings.BIN_C_UNDERCUT_ATR_MAX * atr
    box_height = float(R) - float(S)
    max_box_undercut = (
        settings.BIN_C_UNDERCUT_BOX_MAX * box_height
        if _finite(box_height) and box_height > 0
        else None
    )
    drop_min = settings.BIN_C_V_DROP_ATR_MIN * atr
    rec_min = settings.BIN_C_V_RECOVERY_ATR_MIN * atr
    shoulder = int(settings.BIN_C_V_SHOULDER_BARS)

    lows = df["Low"].values.astype(float)
    highs = df["High"].values.astype(float)
    closes = df["Close"].values.astype(float)

    best = None
    for idx in range(late_start, n):
        low = lows[idx]
        if not np.isfinite(low) or low >= float(S):
            continue
        # (1) undercut floor + breakdown / box caps
        depth = float(S) - low
        if depth < min_undercut or depth > max_undercut:
            continue
        if max_box_undercut is not None and depth > max_box_undercut:
            continue
        # tip = a genuine local Low (nothing lower on the immediate left)
        left0 = max(box_start, idx - shoulder)
        if low > lows[left0:idx + 1].min() + 1e-9:
            continue
        # (2) V arms: a real reaction down into the tip and recovery up out of it
        left_high = float(highs[left0:idx + 1].max())
        right_high = float(highs[idx:min(n, idx + shoulder + 1)].max())
        if (left_high - low) < drop_min or (right_high - low) < rec_min:
            continue
        # (3) reclaim: Close back above S within the recovery window
        recovery_idx = None
        for ridx in range(idx, min(n, idx + settings.BIN_C_RECOVERY_BARS_MAX + 1)):
            if closes[ridx] >= float(S):
                recovery_idx = ridx
                break
        if recovery_idx is None:
            continue
        cand = {"idx": idx, "recovery_idx": recovery_idx, "undercut_atr": depth / atr}
        # prefer the latest, then deepest qualifying spring (closest to launch)
        if best is None or (cand["idx"], cand["undercut_atr"]) > (best["idx"], best["undercut_atr"]):
            best = cand

    if best is None:
        return empty

    idx = int(best["idx"])
    recovery_idx = int(best["recovery_idx"])
    denom = max(1, base_len - 1)
    event_seg = df.iloc[idx:recovery_idx + 1]
    return {
        "bin_c_present": True,
        "bin_c_type": "SPRING",
        "bin_c_event_date": _date_at(df, idx),
        "bin_c_event_bar": idx,
        "bin_c_undercut_atr": _round(best["undercut_atr"]),
        "bin_c_recovery_bars": int(recovery_idx - idx),
        "bin_c_recovery_bar": recovery_idx,
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
    phase_a_end_bar: Optional[int] = None,
    v_tip_bar: Optional[int] = None,
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
        phase_a_end_bar: optional df-positional end of the root swing (usually
            the AR). When present, Bin A measures only the climax -> reaction
            bridge while Bin B still measures the validated equilibrium body.
        lps_offset, lps_length: locate the LPS window — it ends at
            len(df) - lps_offset (exclusive) and spans lps_length bars.
        R, S: box ceiling / floor prices (for LPS position + stretch).
        atr_val: ATR snapshot used to normalize the Last-Supper stretch.
        support_test_start_bar: optional df-positional start of a measured
            right-side support-test cluster; used only to locate Bin D when no
            inner box exists.
        v_tip_bar: optional df-positional final recovered low in the late base.
            Used as the Phase B->D divider when no true Phase-C spring exists.
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
    a1_source = phase_a_end_bar if phase_a_end_bar is not None else phase_b_start_bar
    a1 = a1_source if (a1_source is not None and 0 < a1_source <= n) else None
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
    phase_c = _phase_c_candidate(
        df, seg_b, box_start=box_start, base_len=base_len,
        R=R, S=S, atr_val=atr_val,
    )
    out.update(phase_c)
    phase_c_recovery_bar = (
        phase_c.get("bin_c_recovery_bar")
        if phase_c.get("bin_c_type") == "SPRING"
        else None
    )

    # ── Bin D — the right-most Phase D region (shared boundary rule) ────────
    b = phase_b_start_bar if (phase_b_start_bar is not None and 0 <= phase_b_start_bar < n) else None
    d = _resolve_phase_d_start(
        box_start=box_start, base_len=base_len, last=last,
        is_inner_box=is_inner_box, has_lps_window=has_lps,
        lps_start=lps_start, b=b, phase_d_start_bar=phase_d_start_bar,
        support_test_start_bar=support_test_start_bar,
        phase_c_recovery_bar=phase_c_recovery_bar,
        v_tip_bar=v_tip_bar,
    )
    vd = None
    if d is not None and d < n:
        seg_d = df.iloc[d:n]
        vd = _mean_vol(seg_d)
        out["bin_d_start_bar"] = int(d)
        out["bin_d_bars"] = int(n - d)
        out["bin_d_range_pct"] = _range_pct(seg_d)
        out["bin_d_boundary_source"] = (
            "spring" if phase_c_recovery_bar is not None
            else "inner_box" if (is_inner_box or phase_d_start_bar is not None)
            else "v_tip" if v_tip_bar is not None
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

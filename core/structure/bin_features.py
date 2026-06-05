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
    Bin D   — the right-most launchpad. Boundary comes from the SAME rule the
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

PURE MEASUREMENT. No opinion, no gate, never imports the scoring or archive
layers. Returns un-prefixed keys; the pipeline maps them to ``_bin_*`` /
``_lps_*`` archive fields.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from core.structure.scope import _resolve_phase_d_start


def _empty() -> dict:
    return {
        "bin_a_bars": None,
        "bin_a_range_pct": None,
        "bin_a_volume_ratio": None,
        "bin_b_bars": None,
        "bin_b_range_pct": None,
        "bin_b_volume_ratio": None,
        "bin_d_bars": None,
        "bin_d_range_pct": None,
        "bin_d_volume_ratio": None,
        "bin_d_boundary_source": None,
        "bin_lps_bars": None,
        "lps_position_in_box": None,
        "bin_d_vs_b_range_ratio": None,
        "bin_d_vs_b_volume_ratio": None,
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
        lps_offset, lps_length: locate the LPS window — it ends at
            len(df) - lps_offset (exclusive) and spans lps_length bars.
        R, S: box ceiling / floor prices (for LPS position + stretch).
        atr_val: ATR snapshot used to normalize the Last-Supper stretch.

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
    box_ok = box_height is not None and box_height > 0

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

    # ── Bin D — the right-most launchpad (shared boundary rule) ─────────────
    b = phase_b_start_bar if (phase_b_start_bar is not None and 0 <= phase_b_start_bar < n) else None
    d = _resolve_phase_d_start(
        box_start=box_start, base_len=base_len, last=last,
        is_inner_box=is_inner_box, has_lps_window=has_lps,
        lps_start=lps_start, b=b,
    )
    vd = None
    if d is not None and d < n:
        seg_d = df.iloc[d:n]
        vd = _mean_vol(seg_d)
        out["bin_d_bars"] = int(n - d)
        out["bin_d_range_pct"] = _range_pct(seg_d)
        out["bin_d_boundary_source"] = "inner_box" if is_inner_box else "heuristic"
        if vd is not None and vol_ref:
            out["bin_d_volume_ratio"] = _round(vd / vol_ref)

    # ── D-vs-B comparisons (the "is the launchpad tighter/quieter?" read) ───
    if out["bin_d_range_pct"] is not None and out["bin_b_range_pct"]:
        out["bin_d_vs_b_range_ratio"] = _round(out["bin_d_range_pct"] / out["bin_b_range_pct"])
    if vd is not None and vb:
        out["bin_d_vs_b_volume_ratio"] = _round(vd / vb)

    # ── LPS position in the box + Last-Supper stretch ───────────────────────
    if lps_low is not None and box_ok:
        out["lps_position_in_box"] = _round((lps_low - S) / box_height)
        # Stretch = how far the LPS foot sits ABOVE the box ceiling R (the energy
        # source). <=0 -> LPS in/below the box (no over-extension); large +ve ->
        # stretched far above = Last-Supper risk.
        out["lps_stretch_box"] = _round((lps_low - R) / box_height)
    if lps_low is not None and has_atr:
        out["lps_stretch_atr"] = _round((lps_low - R) / float(atr_val))

    return out

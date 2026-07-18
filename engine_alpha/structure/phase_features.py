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
    Bin D   — the right-most Phase D region. Boundary comes from the SAME shared
              rule the scoping overlay draws (``phase_d.resolve_phase_d_boundary``
              via ``scope._resolve_phase_d_start``), so the drawn band and this
              measured bin can never drift apart. Tagged ``bin_d_boundary_source``
              = the EARLIEST credible right-side evidence after the spring-recovery
              floor: "support_tests" (support / rising-support / SOS cluster),
              "inner_box" (a real mini-consolidation), or "v_tip" (final recovered
              V-tip) — else "lps" (the mandatory gate / fallback). A spring
              recovery only FLOORS the search; it is never itself the source.
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

import json
from typing import Optional

import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.box_events import _DETECT
from engine_alpha.structure.metrics import measure_support_slope
from engine_alpha.structure.phase_d import resolve_phase_d_boundary


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
        "phase_d_evidence_json": None,
        "bin_lps_bars": None,
        "lps_position_in_box": None,
        "bin_d_vs_b_range_ratio": None,
        "bin_d_vs_b_volume_ratio": None,
        "bin_d_vs_b_support_quality_delta": None,
        "lps_stretch_atr": None,
        "lps_stretch_box": None,
        "last_supper_pullback_from_extension_pct": None,
        "last_supper_source_box_age": None,
        "last_supper_reclaim_quality": None,
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
    settle", exactly like measure_dwell_balance's dwell). It is deliberately NOT a
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


def _bar_or_none(value, n: int) -> Optional[int]:
    try:
        bar = int(value)
    except (TypeError, ValueError):
        return None
    if 0 <= bar < n:
        return bar
    return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _spread_at(df: "pd.DataFrame", idx: int) -> Optional[float]:
    try:
        return float(df["High"].iloc[idx]) - float(df["Low"].iloc[idx])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _source_box_exit_bar(df: "pd.DataFrame", start: int, end: int,
                         ceiling: float) -> Optional[int]:
    if not _finite(ceiling):
        return None
    lo = max(0, int(start))
    hi = min(len(df), int(end) + 1)
    if lo >= hi:
        return None
    for idx in range(lo, hi):
        try:
            if float(df["Low"].iloc[idx]) > float(ceiling):
                return idx
        except (KeyError, TypeError, ValueError):
            break
    if "Close" not in df.columns:
        return None
    for idx in range(lo, hi):
        try:
            if float(df["Close"].iloc[idx]) > float(ceiling):
                return idx
        except (TypeError, ValueError):
            return None
    return None


def _last_supper_measurements(
    df: "pd.DataFrame",
    *,
    anchor_bar: Optional[int],
    low_bar: Optional[int],
    lps_end: int,
    box_start: int,
    active_R: float,
) -> dict:
    out = {
        "last_supper_pullback_from_extension_pct": None,
        "last_supper_source_box_age": None,
        "last_supper_reclaim_quality": None,
    }
    n = len(df) if df is not None else 0
    if n == 0 or anchor_bar is None or low_bar is None:
        return out
    if not (0 <= anchor_bar < n and 0 <= low_bar < n):
        return out
    try:
        anchor_high = float(df["High"].iloc[anchor_bar])
        lps_low = float(df["Low"].iloc[low_bar])
    except (KeyError, TypeError, ValueError):
        return out
    if not (_finite(anchor_high) and _finite(lps_low)) or anchor_high <= 0:
        return out

    swing = anchor_high - lps_low
    if swing > 0:
        out["last_supper_pullback_from_extension_pct"] = _round(swing / anchor_high)
        final_bar = max(low_bar, min(n - 1, int(lps_end) - 1))
        try:
            final_close = float(df["Close"].iloc[final_bar])
        except (KeyError, TypeError, ValueError):
            final_close = lps_low
        reclaim = _clamp01((final_close - lps_low) / swing)
        final_spread = _spread_at(df, final_bar)
        prev_spread = _spread_at(df, final_bar - 1) if final_bar > low_bar else final_spread
        if final_spread is not None and prev_spread is not None and final_spread > prev_spread:
            spread_quality = _clamp01(1.0 - ((final_spread - prev_spread) / max(final_spread, 1e-9)))
        else:
            spread_quality = 1.0
        out["last_supper_reclaim_quality"] = _round((reclaim + spread_quality) / 2.0)

    if _finite(active_R) and lps_low > float(active_R):
        exit_bar = _source_box_exit_bar(df, box_start, low_bar, float(active_R))
        if exit_bar is not None:
            out["last_supper_source_box_age"] = int(low_bar - exit_bar)

    return out


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
    """Measure the Phase-C spring: a bounded EXCURSION below support that is
    reclaimed and HELD.

    A spring is a phase, not a one-bar V. Price penetrates support (the test),
    then climbs back into the range and holds there (supply absorbed). The
    excursion can be a clean fast V or a choppy linger below S — both are valid;
    we validate the invariants, shape-agnostic:

      1. penetration — a tip Low dips >= BIN_C_UNDERCUT_ATR_MIN below S and no
                       deeper than the breakdown caps (BIN_C_UNDERCUT_ATR_MAX and
                       BIN_C_UNDERCUT_BOX_MAX).
      2. reclaim     — Close climbs back above S within BIN_C_RECOVERY_BARS_MAX
                       bars of the tip, and the whole below-S episode (first
                       penetration -> reclaim) is bounded by BIN_C_LINGER_BARS_MAX.
      3. significance— not a trivial one-bar poke: EITHER a visible clean-V dip
                       (>= BIN_C_SIGNIF_UNDERCUT_ATR) OR a multi-bar struggle below
                       S (episode spans >= BIN_C_MIN_LINGER_BARS).
      4. hold        — after the reclaim, Close HOLDS above S for BIN_C_HOLD_BARS
                       bars (one dip up to BIN_C_HOLD_TOL_ATR below S is tolerated
                       as a secondary test). This is the absorption confirmation —
                       it rejects the poke-and-fail that looks like a spring for
                       one bar then breaks back down.

    All depth thresholds are ATR-normalized. Most bases have no Phase C and that
    is normal. Pure measurement; never gates score/tier.
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
    Sf = float(S)
    late_start = box_start + int(base_len * settings.BIN_C_LATE_BOX_FRACTION)
    late_start = max(box_start + 1, min(late_start, n - 1))
    min_undercut = settings.BIN_C_UNDERCUT_ATR_MIN * atr
    max_undercut = settings.BIN_C_UNDERCUT_ATR_MAX * atr
    box_height = float(R) - Sf
    max_box_undercut = (
        settings.BIN_C_UNDERCUT_BOX_MAX * box_height
        if _finite(box_height) and box_height > 0
        else None
    )
    reclaim_max = int(settings.BIN_C_RECOVERY_BARS_MAX)
    linger_max = int(settings.BIN_C_LINGER_BARS_MAX)
    hold_bars = int(settings.BIN_C_HOLD_BARS)
    hold_tol = settings.BIN_C_HOLD_TOL_ATR * atr
    signif_undercut = settings.BIN_C_SIGNIF_UNDERCUT_ATR * atr
    min_linger = int(settings.BIN_C_MIN_LINGER_BARS)

    lows = df["Low"].values.astype(float)
    closes = df["Close"].values.astype(float)

    def _spring_at(tip):
        """Validate a spring episode whose trough is bar ``tip``; None if not one."""
        low = lows[tip]
        if not np.isfinite(low) or low >= Sf:
            return None
        # (1) penetration: a real test, not a touch, and not a breakdown
        depth = Sf - low
        if depth < min_undercut or depth > max_undercut:
            return None
        if max_box_undercut is not None and depth > max_box_undercut:
            return None
        # (2) reclaim: first Close back above S, within the window
        reclaim = None
        for r in range(tip, min(n, tip + reclaim_max + 1)):
            if closes[r] >= Sf:
                reclaim = r
                break
        if reclaim is None:
            return None
        # the below-S episode (first penetration -> reclaim) must be bounded, and
        # the tip must be its genuine trough (the deepest Low of the sojourn)
        start = tip
        while start - 1 > box_start and lows[start - 1] < Sf:
            start -= 1
        if (reclaim - start) > linger_max:
            return None
        # tip must be the deepest Low of the sojourn (inclusive of the reclaim
        # bar, so a single wick-below-then-close-above spring — start==reclaim — is
        # a non-empty slice rather than an error)
        if low > lows[start:reclaim + 1].min() + 1e-9:
            return None
        # (3) significance: not a trivial one-bar poke. EITHER a visible clean-V
        # dip (deep enough on its own) OR a genuine multi-bar struggle below S (the
        # episode lingers) — the user's "not a simple bar breach and recovery".
        if depth < signif_undercut and (reclaim - start) < min_linger:
            return None
        # (4) hold: the reclaim must STICK — Close stays above S (one tolerated
        # secondary-test dip) over the next hold_bars bars (or to the right edge)
        dips = 0
        for h in range(reclaim + 1, min(n, reclaim + 1 + hold_bars)):
            c = closes[h]
            if c >= Sf:
                continue
            if c >= Sf - hold_tol and dips == 0:
                dips += 1
                continue
            return None
        return {"idx": tip, "recovery_idx": reclaim, "undercut_atr": depth / atr}

    best = None
    for idx in range(late_start, n):
        cand = _spring_at(idx)
        if cand is None:
            continue
        # prefer the latest, then deepest qualifying spring (closest to launch)
        if best is None or (cand["idx"], cand["undercut_atr"]) > (best["idx"], best["undercut_atr"]):
            best = cand

    if best is None:
        # Flag-dark terminal-shakeout fallback (Event Map Task 11 tail): a
        # violent, later-reclaimed excursion the calibrated spring caps
        # rightly refuse (depth/linger are breakdown defenses) can still BE
        # the box's Phase C at terminal-shakeout scale — the operator's BODI
        # ruling ("not a box break"). Consulted only when the ordinary
        # detector finds nothing, so no calibrated SPRING can ever be
        # re-typed; feeding it HERE (the one Phase-C seam) keeps find_spring,
        # measure_phases, chart labels and the archive in lockstep.
        if settings.BAND_RAILS_ENABLED:
            shakeout = _terminal_shakeout(df, base_seg, box_start=box_start,
                                          base_len=base_len, R=float(R), S=Sf,
                                          atr=atr)
            if shakeout is not None:
                return shakeout
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


def _terminal_shakeout(df: "pd.DataFrame", base_seg: "pd.DataFrame", *,
                       box_start: int, base_len: int, R: float, S: float,
                       atr: float) -> Optional[dict]:
    """Type the box's qualified DEEP excursion as its Phase C
    (``bin_c_type = "TERMINAL_SHAKEOUT"``) — flag-dark, Event Map Task 11.

    Qualification is rail_qualification's own (the SAME read the pair election used):
    every band-leaving span must reclaim/fail-back and HOLD, and a deep
    below-rail event must exist — otherwise there is no event to type. Of
    the qualifying deep events the LAST one is the shakeout (the ordinary
    detector's latest-first preference). Coordinates land in the ordinary
    bin_c shape: the event bar is the excursion's trough, the recovery bar
    is the first close back inside the buffered band (the event's own
    reclaim definition — a hair looser than the ordinary close-above-S)."""
    from engine_alpha.structure.rail_qualification import qualify_pair_events

    window = df.iloc[box_start:]
    read = qualify_pair_events(window, S, R, atr)
    if read is None:
        return None
    event = read["deep"][-1]
    lows = window["Low"].values.astype(float)
    tip_off = event["start"] + int(np.argmin(lows[event["start"]:event["end"]]))
    idx = box_start + tip_off
    recovery_idx = box_start + int(event["reclaim_bar"])
    denom = max(1, base_len - 1)
    event_seg = df.iloc[idx:recovery_idx + 1]
    return {
        "bin_c_present": True,
        "bin_c_type": "TERMINAL_SHAKEOUT",
        "bin_c_event_date": _date_at(df, idx),
        "bin_c_event_bar": idx,
        "bin_c_undercut_atr": _round((float(S) - float(event["extreme"])) / atr),
        "bin_c_recovery_bars": int(recovery_idx - idx),
        "bin_c_recovery_bar": recovery_idx,
        "bin_c_time_loc": _round(np.clip((idx - box_start) / denom, 0.0, 1.0)),
        "bin_c_spring_vol_z": _volume_z(event_seg, base_seg),
    }


# The injection sentinel is box_events._DETECT (imported above): "no spring
# was injected — self-detect", distinct from None ("the walk elected NO Phase
# C"). ONE shared sentinel so both injection seams compare the same identity.
def measure_phases(
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
    sos_reclaim_start_bar: Optional[int] = None,
    rising_support_start_bar: Optional[int] = None,
    phase_a_end_bar: Optional[int] = None,
    v_tip_bar: Optional[int] = None,
    lps_R: Optional[float] = None,
    lps_S: Optional[float] = None,
    lps_anchor_bar: Optional[int] = None,
    lps_low_bar: Optional[int] = None,
    spring=_DETECT,
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
        sos_reclaim_start_bar/rising_support_start_bar: optional df-positional
            starts of richer right-side evidence derived from LPS/Test candidates.
        v_tip_bar: optional df-positional final recovered low in the late base.
            Used as the Phase B->D divider when no true Phase-C spring exists.
        lps_R, lps_S: optional active LPS box ceiling/floor. Parent R/S still
            define Bin B/D; these only define LPS position/stretch when the LPS
            was elected against an inner range.
        lps_anchor_bar/lps_low_bar: optional elected LPS swing bars from
            ``detect_lps``. When present, Last Supper measurements use the
            anchor High -> elected valley Low rather than re-inferring from the
            LPS window.
        spring: the engine's elected Phase-C ``Spring`` brick, or None when the
            walk found no Phase C. The default ``_DETECT`` self-detects via
            ``_phase_c_candidate`` (the measure-only path, unchanged); the live
            chain injects ``structure.spring`` so the one elected Phase-C
            answer is never re-derived.

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
    elected_lps_low_bar = None
    elected_lps_anchor_bar = None
    if has_lps:
        seg_lps = df.iloc[lps_start:lps_end]
        try:
            low_values = seg_lps["Low"].values.astype(float)
            high_values = seg_lps["High"].values.astype(float)
            if not np.isfinite(low_values).any() or not np.isfinite(high_values).any():
                raise ValueError("non-finite LPS window")
            fallback_low_rel = int(np.nanargmin(low_values))
            fallback_low_bar = lps_start + fallback_low_rel
            elected_lps_low_bar = _bar_or_none(lps_low_bar, n)
            if elected_lps_low_bar is None or not (lps_start <= elected_lps_low_bar < lps_end):
                elected_lps_low_bar = fallback_low_bar
            elected_lps_anchor_bar = _bar_or_none(lps_anchor_bar, n)
            if elected_lps_anchor_bar is None or not (lps_start <= elected_lps_anchor_bar < lps_end):
                fallback_anchor_rel = int(np.nanargmax(high_values))
                elected_lps_anchor_bar = lps_start + fallback_anchor_rel
            lps_low = float(df["Low"].iloc[elected_lps_low_bar])
        except (KeyError, ValueError, TypeError):
            lps_low = None
            elected_lps_low_bar = None
            elected_lps_anchor_bar = None
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
    if spring is _DETECT:
        phase_c = _phase_c_candidate(
            df, seg_b, box_start=box_start, base_len=base_len,
            R=R, S=S, atr_val=atr_val,
        )
    elif spring is None:
        phase_c = {}   # no Phase C: out already holds _empty()'s bin_c keys
    else:
        # The elected brick carries its detector's own bin_c dict
        # (``Spring.detection``, stored at election) — injected verbatim, so
        # there is no field-by-field inverse map to keep in sync.
        phase_c = spring.detection
    out.update(phase_c)
    phase_c_recovery_bar = (
        phase_c.get("bin_c_recovery_bar")
        if phase_c.get("bin_c_type") == "SPRING"
        else None
    )

    # ── Bin D — the right-most Phase D region (shared boundary rule) ────────
    b = phase_b_start_bar if (phase_b_start_bar is not None and 0 <= phase_b_start_bar < n) else None
    inner_start = box_start if (is_inner_box and phase_d_start_bar is None) else phase_d_start_bar
    phase_d = resolve_phase_d_boundary(
        last=last,
        has_lps_window=has_lps,
        lps_start=lps_start,
        b=b,
        phase_c_recovery_bar=phase_c_recovery_bar,
        phase_d_start_bar=inner_start,
        v_tip_bar=v_tip_bar,
        support_test_start_bar=support_test_start_bar,
        sos_reclaim_start_bar=sos_reclaim_start_bar,
        rising_support_start_bar=rising_support_start_bar,
    )
    d = phase_d.start_bar
    vd = None
    if d is not None and d < n:
        seg_d = df.iloc[d:n]
        vd = _mean_vol(seg_d)
        out["bin_d_start_bar"] = int(d)
        out["bin_d_bars"] = int(n - d)
        out["bin_d_range_pct"] = _range_pct(seg_d)
        out["bin_d_boundary_source"] = phase_d.source
        out["phase_d_evidence_json"] = json.dumps(phase_d.evidence, sort_keys=True)
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

    if has_lps:
        out.update(_last_supper_measurements(
            df,
            anchor_bar=elected_lps_anchor_bar,
            low_bar=elected_lps_low_bar,
            lps_end=lps_end,
            box_start=box_start,
            active_R=active_R,
        ))

    return out

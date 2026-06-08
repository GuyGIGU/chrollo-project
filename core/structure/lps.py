"""
LPS / spring detection - the Last-Point-of-Support finder.

Part of the Visual Structure Engine: given an already-detected consolidation
box (its R, S, ATR and base length), this scans recent bars for a valid Last
Point of Support: the quiet, tight pullback that marks the launch pad before a
breakout. It also classifies the zone the pullback sits in:

    INSIDE       -> pullback low sits between S and R (textbook LPS)
    OVERSHOOT_R  -> pullback pokes just above R then holds (backtest of breakout)
    UNDERCUT_S   -> pullback dips just below S then reclaims (a spring = REBOUND)

This module is pure measurement + classification. It does not decide how good
the setup is; it returns geometry/behavior facts and lets scoring grade them.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional, Union

import pandas as pd

from config import settings


def _pairwise_descent_fraction(values) -> float:
    """Fraction of pairwise comparisons where later values do not rise."""
    n = len(values)
    if n < 2:
        return 1.0
    total_pairs = n * (n - 1) // 2
    concordant = 0
    for i in range(n):
        for j in range(i + 1, n):
            if values[j] <= values[i]:
                concordant += 1
    return concordant / total_pairs if total_pairs > 0 else 1.0


def _zone_tolerance(sup_avg: float, res_avg: float, atr_val: float) -> float:
    """Tolerance around the active box used by the LPS zone gate."""
    box_height = res_avg - sup_avg
    bw = box_height / sup_avg if sup_avg > 0 else 0.0
    if bw < 0.10:
        return max(settings.LPS_ZONE_ATR_MULT * atr_val, 0.5 * box_height)
    return settings.LPS_ZONE_ATR_MULT * atr_val


def _date_at(df: pd.DataFrame, idx: int) -> Optional[str]:
    if idx < 0 or idx >= len(df):
        return None
    try:
        return str(df.index[idx])[:10]
    except (IndexError, TypeError, ValueError):
        return None


def _public_candidate(candidate: dict, df: pd.DataFrame) -> dict:
    out = {k: v for k, v in candidate.items() if k != "_quality"}
    start = int(out["start_index"])
    end = int(out["end_index"])
    out["start_date"] = _date_at(df, start)
    out["end_date"] = _date_at(df, end - 1)
    return out


def _collect_lps_candidates(
    df: pd.DataFrame,
    latest: pd.Series,
    sup_avg: float,
    res_avg: float,
    atr_val: float,
    base_range_threshold: float,
    base_len: int,
    swing_complete_idx: int,
    offset_max: int,
    diagnose: bool = False,
) -> tuple[list[dict], Counter]:
    candidates: list[dict] = []
    rejects: Counter = Counter()
    n = len(df)

    box_height = res_avg - sup_avg
    if box_height <= 0:
        if diagnose:
            rejects["box_height_nonpos"] += 1
        return candidates, rejects

    zone_tol = _zone_tolerance(sup_avg, res_avg, atr_val)
    r_ceiling = res_avg + zone_tol
    s_floor = sup_avg - zone_tol

    # LPS must land inside the base + reaction window. Without this guard,
    # raising scan depth could match an LPS that pre-dates the box entirely.
    max_window = base_len + settings.AR_MAX_BARS

    for offset in range(0, max(0, int(offset_max))):
        end = n - offset
        eval_idx = end - 1

        # The LPS must sit after the swing that established both R and S.
        if eval_idx <= swing_complete_idx:
            if diagnose:
                rejects["swing_complete"] += 1
            continue

        for length in range(settings.LPS_LENGTH_MIN, settings.LPS_LENGTH_MAX + 1):
            start = end - length
            if start < 0:
                if diagnose:
                    rejects["start_underflow"] += 1
                continue
            if offset + length > max_window:
                if diagnose:
                    rejects["window_overflow"] += 1
                continue

            pullback_period = df.iloc[start:end]
            end_lps = pullback_period.iloc[-1]

            high_vals = pullback_period["High"].values
            low_vals = pullback_period["Low"].values
            max_high_lps = float(high_vals.max())
            min_low_lps = float(low_vals.min())
            trigger_price = float(end_lps["High"])

            if max_high_lps <= 0:
                if diagnose:
                    rejects["max_high_nonpos"] += 1
                continue

            # A support test should be a reaction into support, not a rising
            # sequence that happens to contain one acceptable low.
            low_descent_frac = _pairwise_descent_fraction(low_vals)
            if low_descent_frac < settings.LPS_MIN_DESCENT_FRAC:
                if diagnose:
                    rejects["shape_up_march"] += 1
                continue

            high_descent_frac = _pairwise_descent_fraction(high_vals)
            if high_descent_frac < settings.LPS_MIN_HIGH_DESCENT_FRAC:
                if diagnose:
                    rejects["high_up_march"] += 1
                continue

            # Zone gate: LPS low must sit in one of the valid support zones.
            if min_low_lps < s_floor or min_low_lps > r_ceiling:
                if diagnose:
                    rejects["zone_gate"] += 1
                continue
            if min_low_lps < sup_avg:
                zone_type = "UNDERCUT_S"
            elif min_low_lps > res_avg:
                zone_type = "OVERSHOOT_R"
            else:
                zone_type = "INSIDE"

            # Behavior gate: the candidate window should localize the support
            # test. If it spans most of the active box, it is a broad reaction
            # region, not a usable LPS footprint.
            window_range_pct_box = (max_high_lps - min_low_lps) / box_height
            if window_range_pct_box > settings.LPS_MAX_WINDOW_BOX_RANGE:
                if diagnose:
                    rejects["window_box_range"] += 1
                continue

            # INSIDE means the low is back inside the old box. If the same
            # window first launched far above R, the chosen block is usually a
            # late pullback/off-structure reaction rather than BUEC behavior.
            high_extension = max(0.0, max_high_lps - res_avg)
            high_extension_box = high_extension / box_height
            high_extension_atr = (
                high_extension / float(atr_val)
                if atr_val is not None and float(atr_val) > 0
                else 0.0
            )
            if (
                zone_type == "INSIDE"
                and high_extension_box > settings.LPS_INSIDE_HIGH_EXTENSION_BOX_MAX
                and high_extension_atr > settings.LPS_INSIDE_HIGH_EXTENSION_ATR_MAX
            ):
                if diagnose:
                    rejects["inside_high_extension"] += 1
                continue

            drop_pct = (max_high_lps - min_low_lps) / max_high_lps
            min_drop = (
                settings.LPS_DROP_MIN_OVERSHOOT_R
                if zone_type == "OVERSHOOT_R"
                else settings.LPS_DROP_MIN
            )
            if not (min_drop <= drop_pct <= settings.LPS_DROP_MAX):
                if diagnose:
                    rejects[f"drop_pct({drop_pct:.3f})"] += 1
                continue

            if base_range_threshold <= 0:
                if diagnose:
                    rejects["base_range_nonpos"] += 1
                continue
            if pullback_period["Spread"].max() >= base_range_threshold:
                if diagnose:
                    rejects["spread_quantile"] += 1
                continue
            tight_spread = end_lps["Spread"]

            if settings.LPS_SPREAD_MUST_DECLINE and length >= 2:
                prev_bar = pullback_period.iloc[-2]
                if tight_spread > prev_bar["Spread"]:
                    if diagnose:
                        rejects["spread_decline"] += 1
                    continue

            vol_50_at_lps = float(df.iloc[eval_idx]["Vol_50"])
            if vol_50_at_lps <= 0:
                if diagnose:
                    rejects["vol50_nonpos"] += 1
                continue
            avg_pullback_vol = pullback_period["Volume"].mean()
            if avg_pullback_vol >= vol_50_at_lps * settings.LPS_VOL_CONTRACTION_MAX:
                if diagnose:
                    rejects["vol_contraction"] += 1
                continue

            if latest["Close"] < (min_low_lps * settings.LPS_HOLD_TOLERANCE):
                if diagnose:
                    rejects["hold_tolerance"] += 1
                continue

            # Bars after the LPS evaluation bar must hold above the LPS low and
            # stay tight, or the "LPS" has become another down-leg.
            if offset > 0:
                post_lps = df.iloc[end:n]
                if post_lps["Low"].min() < min_low_lps * settings.LPS_HOLD_TOLERANCE:
                    if diagnose:
                        rejects["post_lps_low_breach"] += 1
                    continue
                if post_lps["Spread"].max() >= base_range_threshold:
                    if diagnose:
                        rejects["post_lps_spread"] += 1
                    continue

            vol_contraction = (vol_50_at_lps - avg_pullback_vol) / vol_50_at_lps
            if vol_contraction <= 0:
                if diagnose:
                    rejects["vol_contraction_post"] += 1
                continue
            tightness_ratio = tight_spread / base_range_threshold
            quality = (
                vol_contraction
                * (1 - tightness_ratio)
                * low_descent_frac
                * high_descent_frac
            )

            setup_type = "REBOUND" if zone_type == "UNDERCUT_S" else "LPS"
            candidates.append({
                "length": length,
                "offset": offset,
                "start_index": int(start),
                "end_index": int(end),
                "low": min_low_lps,
                "high": max_high_lps,
                "trigger_price": trigger_price,
                "vol_contraction": vol_contraction,
                "tightness_ratio": tightness_ratio,
                "setup_type": setup_type,
                "zone_type": zone_type,
                "descent_frac": low_descent_frac,
                "high_descent_frac": high_descent_frac,
                "window_range_pct_box": window_range_pct_box,
                "high_extension_box": high_extension_box,
                "high_extension_atr": high_extension_atr,
                "_quality": quality,
            })

    return candidates, rejects


def detect_lps(
    df: pd.DataFrame,
    latest: pd.Series,
    sup_avg: float,
    res_avg: float,
    atr_val: float,
    base_range_threshold: float,
    base_len: int,
    swing_complete_idx: int,
    diagnose: bool = False,
) -> Union[Optional[dict], tuple[Optional[dict], Counter]]:
    """
    Scan the active recent tape for the best valid LPS formation.

    diagnose=True returns (best_candidate_or_None, Counter of rejection reasons)
    for watchlist/backtest harnesses.
    """
    candidates, rejects = _collect_lps_candidates(
        df,
        latest,
        sup_avg,
        res_avg,
        atr_val,
        base_range_threshold,
        base_len,
        swing_complete_idx,
        settings.LPS_SCAN_OFFSET_MAX,
        diagnose,
    )
    if not candidates:
        return (None, rejects) if diagnose else None

    candidates.sort(key=lambda c: c["_quality"], reverse=True)
    best = _public_candidate(candidates[0], df)
    return (best, rejects) if diagnose else best


def detect_lps_tests(
    df: pd.DataFrame,
    latest: pd.Series,
    sup_avg: float,
    res_avg: float,
    atr_val: float,
    base_range_threshold: float,
    base_len: int,
    swing_complete_idx: int,
    max_tests: int = 8,
) -> list[dict]:
    """
    Return non-overlapping support-test/LPS candidates across the base.

    This is a measure-only companion to detect_lps. The live screener still
    elects one active recent LPS, but the UI can draw earlier Phase-D tests so
    the chart reads as behavior/a staircase instead of a single magic block.
    """
    max_window = base_len + settings.AR_MAX_BARS
    offset_max = max(0, max_window - settings.LPS_LENGTH_MIN + 1)
    candidates, _ = _collect_lps_candidates(
        df,
        latest,
        sup_avg,
        res_avg,
        atr_val,
        base_range_threshold,
        base_len,
        swing_complete_idx,
        offset_max,
        diagnose=False,
    )
    if not candidates:
        return []

    selected = []
    used_spans: list[tuple[int, int]] = []
    for candidate in sorted(candidates, key=lambda c: c["_quality"], reverse=True):
        start = int(candidate["start_index"])
        end = int(candidate["end_index"])
        overlaps = any(start < used_end and end > used_start for used_start, used_end in used_spans)
        if overlaps:
            continue
        selected.append(candidate)
        used_spans.append((start, end))
        if len(selected) >= max_tests:
            break

    selected.sort(key=lambda c: c["start_index"])
    return [_public_candidate(candidate, df) for candidate in selected]

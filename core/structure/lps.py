"""
LPS / spring detection — the Last-Point-of-Support finder.

Part of the Visual Structure Engine: given an already-detected consolidation
box (its R, S, ATR and base length), this scans the most recent bars for a
valid Last Point of Support — the quiet, tight pullback that marks the launch
pad just before a breakout. It also classifies the zone the pullback sits in:

    INSIDE       -> pullback low sits between S and R (textbook LPS)
    OVERSHOOT_R  -> pullback pokes just above R then holds (backtest of breakout)
    UNDERCUT_S   -> pullback dips just below S then reclaims (a spring = REBOUND)

This module is pure measurement + classification. It does NOT decide how good
the setup is — it returns the candidate's geometry (where, how deep, how tight,
how clean the descent) and lets the Scoring Engine grade it.
"""
from __future__ import annotations

from collections import Counter
from typing import Optional, Union

import pandas as pd

from config import settings


def detect_lps(df: pd.DataFrame, latest: pd.Series,
               sup_avg: float, res_avg: float,
               atr_val: float, base_range_threshold: float,
               base_len: int, swing_complete_idx: int,
               diagnose: bool = False
               ) -> Union[Optional[dict], tuple[Optional[dict], Counter]]:
    """
    Scan backward through recent bars looking for valid LPS formations.

    Strategy rules (aligned with the user's Wyckoff spec):
      - Zone gate: LPS low must sit in one of three zones relative to the box —
        INSIDE (S..R), OVERSHOOT_R (R..R+k*ATR = backtest of breakout),
        or UNDERCUT_S (S-k*ATR..S = spring).
      - Window bound: the LPS must sit inside the consolidation +
        post-breakout reaction window (base_len + AR_MAX_BARS) so we never
        match an LPS that pre-dates the structural box.
      - Staleness cap: pullback depth from the pivot high stays within
        [LPS_DROP_MIN, LPS_DROP_MAX] so we enter close to the last energy
        gain, not after a stretched move.
      - Spread (core): EVERY bar in the LPS formation must be tighter
        than the P-percentile of all bar ranges across the base (default
        median — "price moves less than most bars in consolidation").
        Plus declining spread (last <= prior) if LPS_SPREAD_MUST_DECLINE.
      - Volume (bare minimum): the pullback's average volume must undercut
        the 50-day average at the LPS evaluation bar — that's the only
        volume gate, because real-life dry-up is too noisy to make a core
        signal.

    Candidates are ranked by volume contraction × spread compression.

    diagnose=True returns (best_candidate_or_None, Counter of rejection
    reasons across all (offset, length) tries) — used by the watchlist
    backtest harnesses to explain misses. Live screener calls with
    diagnose=False (default) and gets the same Optional[dict] as before.
    """
    n = len(df)
    candidates: list[dict] = []
    rejects: Counter = Counter()

    # Tight-box zone-tolerance floor. For Phase D launchpads (bw < 0.10),
    # half-ATR can shrink below half-box-height, suffocating a textbook
    # spring/retest. Floor zone_tol at 0.5 * box_height in that regime.
    # Self-gating: wider boxes keep the flat ATR rule (half-box-height would
    # otherwise let the LPS land mid-box).
    box_height = res_avg - sup_avg
    bw = box_height / sup_avg if sup_avg > 0 else 0.0
    if bw < 0.10:
        zone_tol = max(settings.LPS_ZONE_ATR_MULT * atr_val, 0.5 * box_height)
    else:
        zone_tol = settings.LPS_ZONE_ATR_MULT * atr_val
    r_ceiling = res_avg + zone_tol     # OVERSHOOT_R upper bound
    s_floor = sup_avg - zone_tol       # UNDERCUT_S lower bound

    # LPS must land inside the base + reaction window. Without this guard,
    # bumping LPS_SCAN_OFFSET_MAX during backtests could match an LPS that
    # pre-dates the consolidation entirely.
    max_window = base_len + settings.AR_MAX_BARS

    for offset in range(0, settings.LPS_SCAN_OFFSET_MAX):
        end = n - offset
        eval_idx = end - 1

        # Swing-complete gate: the LPS must sit AFTER the swing that
        # established BOTH R and S. Before that bar there is no
        # consolidation yet — only the leg that defined the box.
        if eval_idx <= swing_complete_idx:
            if diagnose: rejects['swing_complete'] += 1
            continue

        for length in range(settings.LPS_LENGTH_MIN, settings.LPS_LENGTH_MAX + 1):
            start = end - length
            if start < 0:
                if diagnose: rejects['start_underflow'] += 1
                continue
            if offset + length > max_window:
                if diagnose: rejects['window_overflow'] += 1
                continue

            pullback_period = df.iloc[start:end]
            end_lps = pullback_period.iloc[-1]

            high_vals = pullback_period['High'].values
            low_vals = pullback_period['Low'].values
            max_high_lps = float(high_vals.max())
            min_low_lps = float(low_vals.min())

            if max_high_lps <= 0:
                if diagnose: rejects['max_high_nonpos'] += 1
                continue

            # Shape gate (graded): pair-wise descent fraction across lows.
            # For each pair (i<j) we count concordant = later low <= earlier
            # low. descent_frac = concordant / total_pairs, range [0, 1].
            # 1.0 = perfect descent, 0.5 = sideways/random, 0.0 = perfect
            # rally. Replaces the prior binary argmax-high > argmin-low
            # reject, which dropped near-misses like "high at bar 5, low at
            # bar 6" where the rest of the window is cleanly descending.
            # We still reject up-marches (descent_frac < LPS_MIN_DESCENT_FRAC)
            # but use the surviving descent_frac as a quality multiplier so
            # cleaner descents outrank sloppy ones in the candidate ranking.
            if length >= 2:
                total_pairs = length * (length - 1) // 2
                concordant = 0
                for i in range(length):
                    for j in range(i + 1, length):
                        if low_vals[j] <= low_vals[i]:
                            concordant += 1
                descent_frac = concordant / total_pairs if total_pairs > 0 else 1.0
            else:
                descent_frac = 1.0
            if descent_frac < settings.LPS_MIN_DESCENT_FRAC:
                if diagnose: rejects['shape_up_march'] += 1
                continue

            # Zone gate: LPS low must sit in one of the 3 valid zones.
            if min_low_lps < s_floor or min_low_lps > r_ceiling:
                if diagnose: rejects['zone_gate'] += 1
                continue
            if min_low_lps < sup_avg:
                zone_type = "UNDERCUT_S"
            elif min_low_lps > res_avg:
                zone_type = "OVERSHOOT_R"
            else:
                zone_type = "INSIDE"

            drop_pct = (max_high_lps - min_low_lps) / max_high_lps
            # Zone-conditional pullback floor: OVERSHOOT_R (backtest of
            # breakout) requires a deeper drop than INSIDE / UNDERCUT_S.
            # An LPS sitting just above R with only a 2% wiggle is not a
            # real retest — it's drift, and risk vs. trigger gets ugly.
            min_drop = (settings.LPS_DROP_MIN_OVERSHOOT_R
                        if zone_type == "OVERSHOOT_R"
                        else settings.LPS_DROP_MIN)
            if not (min_drop <= drop_pct <= settings.LPS_DROP_MAX):
                if diagnose: rejects[f'drop_pct({drop_pct:.3f})'] += 1
                continue

            # Spread (core quality): every bar in the formation must be
            # tighter than most base bars — rejects LPS windows that
            # contain a single wild swing bar even if the tail tightens.
            if base_range_threshold <= 0:
                if diagnose: rejects['base_range_nonpos'] += 1
                continue
            if pullback_period['Spread'].max() >= base_range_threshold:
                if diagnose: rejects['spread_quantile'] += 1
                continue
            tight_spread = end_lps['Spread']

            # Declining spread — final bar is no wider than the prior bar.
            if settings.LPS_SPREAD_MUST_DECLINE and length >= 2:
                prev_bar = pullback_period.iloc[-2]
                if tight_spread > prev_bar['Spread']:
                    if diagnose: rejects['spread_decline'] += 1
                    continue

            # Volume: bare-minimum floor — pullback avg volume < max threshold.
            # Vol_50 is sampled at the LPS evaluation bar (not `latest`) so the
            # gate and the score below reference the same denominator.
            vol_50_at_lps = float(df.iloc[eval_idx]['Vol_50'])
            if vol_50_at_lps <= 0:
                if diagnose: rejects['vol50_nonpos'] += 1
                continue
            avg_pullback_vol = pullback_period['Volume'].mean()
            if avg_pullback_vol >= vol_50_at_lps * settings.LPS_VOL_CONTRACTION_MAX:
                if diagnose: rejects['vol_contraction'] += 1
                continue

            if latest['Close'] < (min_low_lps * settings.LPS_HOLD_TOLERANCE):
                if diagnose: rejects['hold_tolerance'] += 1
                continue

            # Post-LPS continuation guard: bars after the LPS evaluation bar
            # must hold above the LPS low and stay tight. Catches cases like
            # MSGM where a tight 2-bar pullback is followed by widening
            # down-bars that turn the formation into another down-leg.
            if offset > 0:
                post_lps = df.iloc[end:n]
                if post_lps['Low'].min() < min_low_lps * settings.LPS_HOLD_TOLERANCE:
                    if diagnose: rejects['post_lps_low_breach'] += 1
                    continue
                if post_lps['Spread'].max() >= base_range_threshold:
                    if diagnose: rejects['post_lps_spread'] += 1
                    continue

            vol_contraction = (vol_50_at_lps - avg_pullback_vol) / vol_50_at_lps
            # The volume gate above guarantees this mathematically, but use a
            # runtime check rather than assert so `python -O` can't strip it.
            if vol_contraction <= 0:
                if diagnose: rejects['vol_contraction_post'] += 1
                continue
            tightness_ratio = tight_spread / base_range_threshold
            # Quality ranking includes descent_frac so cleaner pullback
            # shapes outrank sloppier ones at the same vol/tightness.
            quality = vol_contraction * (1 - tightness_ratio) * descent_frac

            # REBOUND = undercut-support zone (spring); LPS = the other two.
            setup_type = "REBOUND" if zone_type == "UNDERCUT_S" else "LPS"

            candidates.append({
                'length': length,
                'offset': offset,
                'trigger_price': max_high_lps,
                'vol_contraction': vol_contraction,
                'tightness_ratio': tightness_ratio,
                'setup_type': setup_type,
                'zone_type': zone_type,
                'descent_frac': descent_frac,
                '_quality': quality,
            })

    if not candidates:
        return (None, rejects) if diagnose else None

    candidates.sort(key=lambda c: c['_quality'], reverse=True)
    best = candidates[0]
    del best['_quality']
    return (best, rejects) if diagnose else best

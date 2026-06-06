#!/usr/bin/env python3
"""Backtest the live screener against a list of (ticker, added_date) pairs.

For each entry, evaluates the screener on bars in a [-7, +3] day window
around the added date and reports whether a signal would have fired on any
bar in that window, plus the rejection reason for misses.

Status — banked at 28/44 hits (63.6%) against the seed watchlist (post-shape-gate).

Two LPS-scaling adaptations live in this harness (NOT in the live screener)
to make Phase D launchpad LPSes detectable:

  1. Zone tolerance floor (gated on bw < 0.10):
         zone_tol = max(LPS_ZONE_ATR_MULT * atr, 0.5 * box_height)
     For tight inner boxes the LPS often forms as a breakout-retest just
     above R (or a sellers-failing test just below S). Half-ATR alone is
     too narrow when box_height is small. The bw < 0.10 gate prevents
     over-loosening on wide outer boxes (where half-box-height becomes
     several ATRs of slack). See detect_lps diagnose mode.

  2. Base range threshold floor:
         base_range_threshold = max(spread_quantile, 1.2 * atr)
     Tight inner boxes have a tiny 50%ile spread; an ATR-typical bar in
     the LPS window kills detection without this floor. Self-gates on
     wide-bar bases (the percentile rule still binds). See _evaluate_with_reason.

Remaining 13 misses categorize as:
  - Anchor mis-detection (NBR, GXO, VLO, SHEL): outer-box detector picks
    the wrong window. Not solvable by LPS tuning alone (the v5 recent-first
    anchor experiment was tested and falsified — retired, see git history).
  - Marginal drop_pct edges (TRS at 1.3%, SNDX at 10.6%): structurally
    real bounds — loosening them sacrifices selectivity for two tickers.
  - Spread-decline strict (ST, RRBI): pre-breakout bars not contracting;
    relaxing contradicts the LPS definition.
  - Acceptable misses per project memory (KEYS, BRZU, NE): young-base /
    fast-breakout patterns the screener intentionally does not catch.

Run:
    python -m tools.backtest_watchlist
"""
from __future__ import annotations

import os
import sys
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import settings
from core.scoring import calculate_tier, score_setup
from core.structure import calculate_adx, calculate_atr, detect_lps, find_consolidation

WINDOW_DAYS_BACK = 7    # Look further back to catch pre-breakout state
WINDOW_DAYS_FWD = 3

# (ticker, added_date) — YYYY-MM-DD
WATCHLIST: list[tuple[str, str]] = [
    ("DIBS", "2026-04-14"),
    ("ALB",  "2026-04-13"),
    ("DLX",  "2026-04-13"),
    ("CAPR", "2026-04-13"),
    ("NKTR", "2026-04-13"),
    ("SILC", "2026-04-13"),
    ("ORMP", "2026-04-13"),
    ("MSGS", "2026-04-08"),
    ("DNTH", "2026-04-08"),
    ("LPTH", "2026-04-08"),
    ("SKYT", "2026-04-08"),
    ("CTRI", "2026-04-07"),
    ("KEYS", "2026-04-07"),
    ("PKE",  "2026-04-06"),
    ("BRZU", "2026-03-31"),
    ("RRBI", "2026-03-31"),
    ("DSGN", "2026-03-31"),
    ("PGC",  "2026-03-30"),
    ("EQIX", "2026-03-30"),
    ("EWTX", "2026-03-24"),
    ("NBR",  "2026-03-23"),
    ("NGL",  "2026-03-20"),
    ("NVMI", "2026-03-18"),
    ("NE",   "2026-03-13"),
    ("WDC",  "2026-03-13"),
    ("BWAY", "2026-03-11"),
    ("KALV", "2026-03-09"),
    ("SNDX", "2026-03-06"),
    ("BP",   "2026-03-05"),
    ("VIST", "2026-03-05"),
    ("MEOH", "2026-02-27"),
    ("VLO",  "2026-02-26"),
    ("PKE",  "2026-02-24"),
    ("DRTS", "2026-02-24"),
    ("TERN", "2026-02-23"),
    ("FOSL", "2026-02-18"),
    ("SHEL", "2026-02-18"),
    ("JAZZ", "2026-02-18"),
    ("CGON", "2026-02-17"),
    ("SYRE", "2026-02-12"),
    ("GXO",  "2026-02-11"),
    ("ST",   "2026-02-11"),
    ("TRS",  "2026-02-06"),
    ("GRDN", "2026-02-02"),
]


# Module-level aggregator for cross-ticker rejection counts.
_LPS_GLOBAL_REJECTS: Counter = Counter()


# ---------------------------------------------------------------------------
# Diagnostic evaluator — mirrors _evaluate_ticker but surfaces reject reasons
# ---------------------------------------------------------------------------

def _evaluate_with_reason(df: pd.DataFrame) -> tuple[Optional[dict], Optional[str]]:
    """Run the full screener pipeline against df (last bar = evaluation date).

    Returns (result_dict, None) on pass or (None, reason_str) on reject.
    """
    try:
        if len(df) < 200:
            return None, f"insufficient data ({len(df)} bars)"

        df = df.copy()
        df['SMA_50'] = df['Close'].rolling(window=50).mean()
        df['SMA_200'] = df['Close'].rolling(window=200).mean()
        df['Vol_50'] = df['Volume'].rolling(window=50).mean()
        df['Spread'] = df['High'] - df['Low']
        df['Avg_Spread_20'] = df['Spread'].rolling(window=20).mean()

        latest = df.iloc[-1]
        one_year_ago_idx = max(0, len(df) - 252)
        one_year_ago = df.iloc[one_year_ago_idx]
        yearly_return = (latest['Close'] - one_year_ago['Close']) / one_year_ago['Close']

        if latest['Close'] < settings.MIN_PRICE:
            return None, f"price ${latest['Close']:.2f} < ${settings.MIN_PRICE}"
        if latest['Vol_50'] < settings.MIN_VOLUME_50D:
            return None, f"Vol50 {latest['Vol_50']:.0f} < {settings.MIN_VOLUME_50D}"
        if latest['Close'] < latest['SMA_50']:
            return None, f"below SMA50 ({latest['Close']:.2f} < {latest['SMA_50']:.2f})"
        if latest['Close'] < latest['SMA_200']:
            return None, f"below SMA200 ({latest['Close']:.2f} < {latest['SMA_200']:.2f})"
        if yearly_return < settings.MIN_YEARLY_RETURN:
            return None, f"YoY {yearly_return*100:.1f}% < {settings.MIN_YEARLY_RETURN*100:.0f}%"

        df['ATR_10'] = calculate_atr(df, 10)
        df['ATR_50'] = calculate_atr(df, 50)
        df['ADX_14'] = calculate_adx(df, 14)

        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            _is_inner = \
            find_consolidation(df, min_days=settings.MIN_BASE_DAYS)

        if base_len == 0:
            return None, "no consolidation base found"

        atr_eval = df.iloc[-6]
        atr_ratio = atr_eval['ATR_10'] / atr_eval['ATR_50']

        if latest['Close'] < (sup_avg * settings.CRASH_FILTER_MULT):
            return None, f"crash-filter (price {latest['Close']:.2f} < S*{settings.CRASH_FILTER_MULT:.2f})"
        if latest['Close'] >= (res_avg * settings.EXTENSION_FILTER_MULT):
            return None, f"over-extended (price {latest['Close']:.2f} >= R*{settings.EXTENSION_FILTER_MULT})"

        base_df = df.iloc[-base_len:]
        atr_for_zone = float(atr_eval['ATR_10'])
        # Floor base_range_threshold at 1.2 * ATR. For tight inner boxes,
        # the 50th-percentile spread can be smaller than a normal-volatility
        # bar, which means a single ATR-sized bar in the LPS window kills
        # detection. The floor lets ATR-typical bars pass while the
        # percentile still bounds bases with chronically wide bars.
        base_range_threshold = max(
            float(base_df['Spread'].quantile(settings.LPS_RANGE_PERCENTILE)),
            1.2 * atr_for_zone,
        )
        phase_b_start = len(df) - base_len
        swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)
        lps_result, lps_rejects = detect_lps(
            df, latest, sup_avg, res_avg,
            atr_for_zone, base_range_threshold, base_len, swing_complete_idx,
            diagnose=True,
        )

        if not lps_result:
            _LPS_GLOBAL_REJECTS.update(lps_rejects)
            top = lps_rejects.most_common(2)
            top_str = ", ".join(f"{name}={cnt}" for name, cnt in top) or "no candidates"
            return None, f"no LPS ({top_str})"

        setup_state = lps_result['setup_type']
        lps_length = lps_result['length']
        trigger_price = lps_result['trigger_price']
        vol_contraction = lps_result['vol_contraction']
        tightness_ratio = lps_result['tightness_ratio']

        current_price = latest['Close']
        distance_to_trigger = (trigger_price - current_price) / current_price
        if distance_to_trigger <= 0:
            return None, "LPS already above trigger"

        score_result = score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
        )
        score = score_result['total']
        tier = calculate_tier(score)

        return {
            'Tier': tier,
            'Setup': setup_state,
            'Score': score,
            'Price': round(float(current_price), 2),
            'BaseLen': int(base_len),
            'BoxWidth': round(float(box_width), 3),
            'Touches': int(r_touches + s_touches),
            'LPSLen': int(lps_length),
        }, None

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError) as e:
        return None, f"error: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Data loader — one yfinance batch, split per ticker
# ---------------------------------------------------------------------------

def _download_universe(tickers: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
    print(f"Downloading {len(tickers)} tickers from {start} -> {end} ...")
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        group_by='ticker',
        threads=True,
        progress=False,
        auto_adjust=True,
    )

    out: dict[str, pd.DataFrame] = {}
    if len(tickers) == 1:
        df = raw.dropna()
        if not df.empty:
            out[tickers[0]] = df
    else:
        for t in tickers:
            try:
                df = raw[t].dropna()
                if not df.empty:
                    out[t] = df
            except KeyError:
                pass
    print(f"  Got data for {len(out)}/{len(tickers)} tickers.")
    return out


# ---------------------------------------------------------------------------
# Main backtest driver
# ---------------------------------------------------------------------------

def run_backtest() -> None:
    unique_tickers = sorted({t for t, _ in WATCHLIST})
    earliest = min(pd.Timestamp(d) for _, d in WATCHLIST)
    latest = max(pd.Timestamp(d) for _, d in WATCHLIST)

    # 2y of history before the earliest eval date (need >=200 trading bars)
    start = (earliest - pd.Timedelta(days=365 * 2 + 30)).strftime('%Y-%m-%d')
    end = (latest + pd.Timedelta(days=WINDOW_DAYS_FWD + 2)).strftime('%Y-%m-%d')

    data = _download_universe(unique_tickers, start, end)

    rows: list[dict] = []
    for ticker, added_str in WATCHLIST:
        if ticker not in data:
            rows.append({'Ticker': ticker, 'Added': added_str, 'Result': 'NO_DATA'})
            continue

        df_full = data[ticker]
        added_date = pd.Timestamp(added_str)

        best: Optional[dict] = None
        best_offset: Optional[int] = None
        last_reason = "window empty"

        for offset in range(-WINDOW_DAYS_BACK, WINDOW_DAYS_FWD + 1):
            eval_date = added_date + pd.Timedelta(days=offset)
            df_slice = df_full[df_full.index <= eval_date]
            if len(df_slice) < 200:
                last_reason = f"insufficient data at {eval_date.date()}"
                continue

            result, reason = _evaluate_with_reason(df_slice)
            if result is not None:
                if best is None or result['Score'] > best['Score']:
                    best = result
                    best_offset = offset
            else:
                last_reason = reason

        if best:
            rows.append({
                'Ticker': ticker, 'Added': added_str, 'Result': 'HIT',
                'Offset': best_offset, 'Tier': best['Tier'],
                'Setup': best['Setup'], 'Score': best['Score'],
                'Price': best['Price'], 'BaseLen': best['BaseLen'],
                'BoxW': best['BoxWidth'], 'Touches': best['Touches'],
                'LPSLen': best['LPSLen'], 'Reason': '',
            })
        else:
            rows.append({
                'Ticker': ticker, 'Added': added_str, 'Result': 'MISS',
                'Offset': '', 'Tier': '', 'Setup': '', 'Score': '',
                'Price': '', 'BaseLen': '', 'BoxW': '', 'Touches': '',
                'LPSLen': '', 'Reason': last_reason,
            })

    df = pd.DataFrame(rows)
    hits = df[df['Result'] == 'HIT']
    misses = df[df['Result'] == 'MISS']
    no_data = df[df['Result'] == 'NO_DATA']

    print("\n" + "=" * 88)
    print(f"BACKTEST SUMMARY: {len(hits)}/{len(df)} hits "
          f"({100 * len(hits) / max(len(df), 1):.1f}%)  |  "
          f"{len(misses)} misses  |  {len(no_data)} no-data")
    print("=" * 88)

    if not hits.empty:
        print("\n--- HITS ---")
        print(hits[['Ticker', 'Added', 'Offset', 'Tier', 'Setup', 'Score',
                    'Price', 'BaseLen', 'BoxW', 'Touches', 'LPSLen']].to_string(index=False))

        # Tier breakdown
        tier_counts = hits['Tier'].value_counts().sort_index()
        print("\nTier distribution:")
        for tier, cnt in tier_counts.items():
            print(f"  {tier}: {cnt}")

        # Setup breakdown
        setup_counts = hits['Setup'].value_counts()
        print("\nSetup distribution:")
        for setup, cnt in setup_counts.items():
            print(f"  {setup}: {cnt}")

    if not misses.empty:
        print("\n--- MISSES ---")
        print(misses[['Ticker', 'Added', 'Reason']].to_string(index=False))

        # Reason categories
        def categorize(r: str) -> str:
            rl = r.lower()
            if 'sma' in rl: return 'below moving avg'
            if 'yoy' in rl or 'yearly' in rl: return 'weak YoY'
            if 'price $' in rl: return 'price too low'
            if 'vol50' in rl: return 'low volume'
            if 'consolidation' in rl: return 'no base'
            if 'adx' in rl: return 'trending (ADX)'
            if 'over-extended' in rl: return 'over-extended'
            if 'crash' in rl: return 'crash filter'
            if 'no lps' in rl: return 'no LPS/breakout'
            if 'already above trigger' in rl: return 'past trigger'
            return 'other'
        miss_cat = misses['Reason'].apply(categorize).value_counts()
        print("\nMiss reasons:")
        for cat, cnt in miss_cat.items():
            print(f"  {cat}: {cnt}")

        if _LPS_GLOBAL_REJECTS:
            print("\nLPS gate-failure tally (across all 'no LPS' tickers, all offset/length combos):")
            for gate, cnt in _LPS_GLOBAL_REJECTS.most_common():
                print(f"  {gate}: {cnt}")

    if not no_data.empty:
        print("\n--- NO DATA ---")
        print(no_data[['Ticker', 'Added']].to_string(index=False))

    out_dir = os.path.join(PROJECT_ROOT, 'output', 'backtest')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'watchlist_backtest.csv')
    df.to_csv(out_path, index=False)
    print(f"\nFull results saved to {out_path}")


if __name__ == '__main__':
    run_backtest()

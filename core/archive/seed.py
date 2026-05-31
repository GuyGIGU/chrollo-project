"""
Seed archive — bootstrap the setup archive with cherry-picked historical setups.

Accepts batches of (ticker, date) pairs for setups you already know worked,
runs the screener retrospectively against historical data, captures the full
structural fingerprint, and computes actual forward returns immediately.

Usage:
    python -m core.archive.seed
    python -m core.archive.seed --force   # overwrite existing entries

Edit SEED_SETUPS below (or import this and call seed_archive() programmatically).
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

from config import settings
from core.archive.forward_returns import _compute_returns
from core.pipeline.screener import apply_baseline_filters
from core.scoring import calculate_tier, score_setup
from core.structure import (
    calculate_atr,
    detect_lps,
    find_outer_box,
    measure_contractions,
    measure_support_slope,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("chrollo.seed")

# ──────────────────────────────────────────────────────────────────
# SEED SETUPS: Cherry-picked (ticker, trigger_date) pairs.
# Date = the day price breached the high of the LPS low bar.
# The script scans backward from this date to find when the
# screener signal would have fired (typically 2-8 days before).
# ──────────────────────────────────────────────────────────────────

SEED_SETUPS: list[tuple[str, str]] = [
    # ─── Batch 1: From backtest_watchlist (watchlist added dates) ───
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

    # ─── Batch 2: User's cherry-picked trigger-date winners ────────
    ("NTCT", "2026-03-16"),
    ("RGR",  "2026-03-13"),
    ("FOSL", "2026-03-30"),
    ("SNDX", "2026-03-06"),
    ("PUMP", "2026-03-11"),
    ("USO",  "2026-02-26"),
    ("XWIN", "2026-03-19"),
    ("GASS", "2026-02-24"),
    ("SHEL", "2026-02-18"),
    ("CGON", "2026-02-17"),
    ("NOK",  "2026-02-17"),
    ("IBP",  "2026-02-03"),
    ("WMT",  "2025-09-11"),
    ("LECO", "2026-01-29"),
    ("BWA",  "2026-01-26"),
    ("NGL",  "2026-01-20"),
]

# Scan window: look 10 days BACK and 3 days forward from the trigger date.
# The screener fires before the trigger — the LPS is identified while
# price is still below the trigger level.
WINDOW_BACK = 10
WINDOW_FWD = 3


def _evaluate_at_date(df: pd.DataFrame, spy_6m_return: float = 0.0) -> Optional[dict]:
    """Run the full screener pipeline against df (last bar = evaluation date).

    Returns the result dict on pass, or None on reject.
    Mirrors _evaluate_ticker but works on a pre-sliced DataFrame.
    """
    try:
        baseline = apply_baseline_filters(df)
        if baseline is None:
            return None
        df, yearly_return = baseline

        latest = df.iloc[-1]
        df_ind = df.copy()
        df_ind["ATR_10"] = calculate_atr(df_ind, 10)
        df_ind["ATR_50"] = calculate_atr(df_ind, 50)

        # find_outer_box never refines to an inner sub-box — its is_inner is
        # always False. We discard it (the seed archive is intentionally a
        # gallery of textbook outer-box setups).
        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            _is_inner = \
            find_outer_box(df_ind, min_days=settings.MIN_BASE_DAYS)

        if base_len == 0:
            return None

        atr_eval = df_ind.iloc[-6]
        atr_ratio = atr_eval["ATR_10"] / atr_eval["ATR_50"]

        if latest["Close"] < (sup_avg * settings.CRASH_FILTER_MULT):
            return None
        if latest["Close"] >= (res_avg * settings.EXTENSION_FILTER_MULT):
            return None

        base_df = df.iloc[-base_len:]
        atr_for_zone = float(atr_eval["ATR_10"])
        # Match the live screener: floor base_range_threshold at 1.2 * ATR so
        # tight Phase-D-style bases don't suffocate the LPS spread gate.
        base_range_threshold = max(
            float(base_df["Spread"].quantile(settings.LPS_RANGE_PERCENTILE)),
            1.2 * atr_for_zone,
        )

        phase_b_start = len(df_ind) - base_len
        swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

        lps_result = detect_lps(df_ind, latest, sup_avg, res_avg, atr_for_zone, base_range_threshold, base_len, swing_complete_idx)

        if not lps_result:
            return None

        setup_state = lps_result["setup_type"]
        is_lps = True
        lps_length = lps_result["length"]
        trigger_price = lps_result["trigger_price"]
        vol_contraction = lps_result["vol_contraction"]
        tightness_ratio = lps_result["tightness_ratio"]

        current_price = latest["Close"]
        distance_to_trigger = (trigger_price - current_price) / current_price
        if distance_to_trigger <= 0:
            return None

        # Soft RS — stock 6m return − SPY 6m return at this historical eval date.
        rs_lookback = settings.RS_LOOKBACK_BARS
        if len(df) > rs_lookback:
            stock_6m_return = (float(current_price) / float(df["Close"].iloc[-rs_lookback - 1]) - 1.0)
        else:
            stock_6m_return = 0.0
        excess_return_6m = stock_6m_return - spy_6m_return

        # 52w high distance — pass into scorer for the high-proximity bonus.
        last_252 = df["High"].iloc[-min(252, len(df)):]
        max_252 = float(last_252.max()) if len(last_252) else 0.0
        dist_52w_high_pct = (
            (float(current_price) - max_252) / max_252 if max_252 > 0 else None
        )

        contraction = measure_contractions(base_df)
        support = measure_support_slope(base_df, atr_for_zone)

        score_result = score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
            excess_return_6m, dist_52w_high_pct,
            None,  # breadth_pct unknown for historical seed dates
            contraction['quality'], support['quality'],
        )
        score = score_result["total"]
        tier = calculate_tier(score)

        # Volume signature at R/S touch bars (mirror of _evaluate_ticker).
        touch_band_vol = settings.TOUCH_TOLERANCE_ATR * atr_for_zone
        r_touch_mask = (base_df["High"] - res_avg).abs() <= touch_band_vol
        s_touch_mask = (base_df["Low"] - sup_avg).abs() <= touch_band_vol
        vol_mean_base = float(base_df["Volume"].mean())
        vol_std_base = float(base_df["Volume"].std())
        r_touch_vol_z = (
            float((base_df.loc[r_touch_mask, "Volume"].mean() - vol_mean_base) / vol_std_base)
            if vol_std_base > 0 and r_touch_mask.any() else None
        )
        s_touch_vol_z = (
            float((base_df.loc[s_touch_mask, "Volume"].mean() - vol_mean_base) / vol_std_base)
            if vol_std_base > 0 and s_touch_mask.any() else None
        )

        return {
            "setup_type": setup_state,
            "tier": tier,
            "score": score,
            "current_price": round(float(current_price), 2),
            "r_level": float(res_avg),
            "s_level": float(sup_avg),
            "trigger_price": float(trigger_price),
            "base_length": int(base_len),
            "box_width": float(box_width),
            "touches": int(r_touches + s_touches),
            "r_touches": int(r_touches),
            "s_touches": int(s_touches),
            "r_anchor": int(r_anchor_bar),
            "s_anchor": int(s_anchor_bar),
            "atr_ratio": float(atr_ratio),
            "lps_length": int(lps_length),
            "breach_days": int(breach_days),
            "vol_contraction": float(vol_contraction),
            "tightness_ratio": float(tightness_ratio),
            "sub_scores": score_result,
            "dist_52w_high_pct": dist_52w_high_pct,
            "excess_return_6m": float(excess_return_6m),
            "bars_since_BC": int(len(df) - bc_anchor_bar),
            "descent_length": int(phase_b_start_bar - bc_anchor_bar),
            "base_date_start": str(base_df.index[0])[:10],
            "base_date_end": str(base_df.index[-1])[:10],
            "base_close_start": float(base_df["Close"].iloc[0]),
            "base_close_end": float(base_df["Close"].iloc[-1]),
            "r_touch_vol_z": r_touch_vol_z,
            "s_touch_vol_z": s_touch_vol_z,
            "lps_descent_frac": float(lps_result.get("descent_frac", 1.0)),
            "lps_zone_type": lps_result.get("zone_type", "INSIDE"),
            "contraction_count": int(contraction["n_contractions"]),
            "contraction_quality": float(contraction["quality"]),
            "final_contraction_depth": (float(contraction["final_depth"])
                                        if contraction["final_depth"] is not None else None),
            "support_slope_atr": (float(support["slope_atr"])
                                  if support["slope_atr"] is not None else None),
            "ascending_support_quality": float(support["quality"]),
        }

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError) as e:
        return None


def seed_archive(
    setups: list[tuple[str, str]] | None = None,
    force: bool = False,
) -> int:
    """Import historical setups into the archive.

    Args:
        setups: List of (ticker, date_str) pairs. Defaults to SEED_SETUPS.
        force: If True, overwrite existing entries.

    Returns:
        Number of setups successfully archived.
    """
    from sqlalchemy.orm import sessionmaker

    from archive_models import (
        SetupArchive,
        get_market_context,
        get_sector_etf,
        get_sector_trend,
    )
    from database import make_sqlite_engine

    if setups is None:
        setups = SEED_SETUPS

    if not setups:
        log.warning("No seed setups defined. Add entries to SEED_SETUPS in core/archive/seed.py.")
        return 0

    db_path = os.path.join(_BACKEND_DIR, "trading_journal.db")
    engine = make_sqlite_engine(db_path)
    SetupArchive.metadata.create_all(bind=engine)
    # Bring schema up to date with any post-initial columns.
    from core.archive.writer import _ensure_new_columns
    _ensure_new_columns(engine)
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()

    # Batch download all tickers
    unique_tickers = sorted({t for t, _ in setups})
    earliest = min(pd.Timestamp(d) for _, d in setups)
    latest = max(pd.Timestamp(d) for _, d in setups)

    dl_start = (earliest - pd.Timedelta(days=365 * 2 + 30)).strftime("%Y-%m-%d")
    dl_end = (latest + pd.Timedelta(days=90)).strftime("%Y-%m-%d")  # Extra for forward returns

    log.info(f"Downloading {len(unique_tickers)} tickers from {dl_start} -> {dl_end}...")
    raw = yf.download(
        unique_tickers, start=dl_start, end=dl_end,
        group_by="ticker", threads=True, progress=False, auto_adjust=True,
    )

    # SPY history for per-date RS computation — same window so any seed eval
    # date can look back RS_LOOKBACK_BARS without falling off the start.
    log.info("Downloading SPY for RS reference...")
    spy_raw = yf.download(
        "SPY", start=dl_start, end=dl_end,
        progress=False, auto_adjust=True, threads=True,
    )
    spy_close_series = spy_raw["Close"] if not spy_raw.empty else None
    if spy_close_series is not None and hasattr(spy_close_series, "columns"):
        spy_close_series = spy_close_series.iloc[:, 0]

    # Parse per-ticker DataFrames
    data: dict[str, pd.DataFrame] = {}
    if len(unique_tickers) == 1:
        df = raw.dropna()
        if not df.empty:
            data[unique_tickers[0]] = df
    else:
        for t in unique_tickers:
            try:
                df = raw[t].dropna()
                if not df.empty:
                    data[t] = df
            except KeyError:
                pass

    log.info(f"Got data for {len(data)}/{len(unique_tickers)} tickers.")

    # Market context cache (by date)
    market_ctx_cache: dict[str, dict] = {}
    sector_cache: dict[str, tuple[str | None, str | None]] = {}

    archived = 0
    seen: set[tuple[str, str]] = set()  # Dedup within batch (SNDX, SHEL, etc. appear in both batches)

    for ticker, date_str in setups:
        # Skip duplicate (ticker, date) within the batch
        key = (ticker, date_str)
        if key in seen:
            continue
        seen.add(key)

        if ticker not in data:
            log.warning(f"  {ticker}: no data, skipping.")
            continue

        df_full = data[ticker]
        target_date = pd.Timestamp(date_str)

        # Scan backward from trigger date to find when the screener signal fired
        # (typically 2-8 days before trigger), plus a small forward buffer
        best_result = None
        best_eval_date = None
        for offset in range(-WINDOW_BACK, WINDOW_FWD + 1):
            eval_date = target_date + pd.Timedelta(days=offset)
            df_slice = df_full[df_full.index <= eval_date]
            if len(df_slice) < 200:
                continue

            # SPY 6m return as of this eval date (None-safe: 0.0 if SPY missing).
            spy_6m = 0.0
            if spy_close_series is not None:
                spy_slice = spy_close_series[spy_close_series.index <= eval_date]
                if len(spy_slice) > settings.RS_LOOKBACK_BARS:
                    spy_6m = float(
                        spy_slice.iloc[-1] / spy_slice.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0
                    )

            result = _evaluate_at_date(df_slice, spy_6m_return=spy_6m)
            if result is not None:
                if best_result is None or result["score"] > best_result["score"]:
                    best_result = result
                    best_eval_date = eval_date

        if best_result is None:
            log.warning(f"  {ticker} @ {date_str}: screener did not fire in -{WINDOW_BACK}/+{WINDOW_FWD}d window.")
            continue

        eval_date_str = best_eval_date.strftime("%Y-%m-%d")

        # Check if already exists (by the actual signal date, not trigger date)
        existing = session.query(SetupArchive).filter_by(ticker=ticker, scan_date=eval_date_str).first()
        if existing and not force:
            log.info(f"  {ticker} @ {eval_date_str}: already in archive, skipping (use --force to overwrite).")
            continue

        # Forward returns (since this is historical, we can compute immediately)
        fwd_df = df_full[df_full.index > best_eval_date]
        fwd_returns = {}
        if not fwd_df.empty:
            hist_df = df_full[df_full.index <= best_eval_date]
            vol_50_at_scan = None
            if "Volume" in hist_df.columns and len(hist_df) >= 50:
                vs = hist_df["Volume"]
                if hasattr(vs, "columns"):
                    vs = vs.iloc[:, 0]
                vol_50_at_scan = float(vs.tail(50).mean())
            fwd_returns = _compute_returns(
                fwd_df, best_result["current_price"], best_result["trigger_price"],
                s_level=best_result.get("s_level"), vol_50_at_scan=vol_50_at_scan,
            )

        # Market context
        if eval_date_str not in market_ctx_cache:
            market_ctx_cache[eval_date_str] = get_market_context(eval_date_str)
        market_ctx = market_ctx_cache[eval_date_str]

        # Sector
        if ticker not in sector_cache:
            etf = get_sector_etf(ticker)
            trend = get_sector_trend(etf, eval_date_str) if etf else None
            sector_cache[ticker] = (etf, trend)
        sector_etf, sector_trend = sector_cache[ticker]

        sub = best_result.get("sub_scores", {})

        values = dict(
            ticker=ticker,
            scan_date=eval_date_str,
            setup_type=best_result["setup_type"],
            tier=best_result["tier"],
            score=best_result["score"],
            current_price=best_result["current_price"],
            r_level=best_result["r_level"],
            s_level=best_result["s_level"],
            trigger_price=best_result["trigger_price"],
            base_length=best_result["base_length"],
            box_width=best_result["box_width"],
            touches=best_result["touches"],
            r_touches=best_result["r_touches"],
            s_touches=best_result["s_touches"],
            r_anchor=best_result.get("r_anchor"),
            s_anchor=best_result.get("s_anchor"),
            atr_ratio=best_result["atr_ratio"],
            lps_length=best_result["lps_length"],
            breach_days=best_result["breach_days"],
            vol_contraction=best_result["vol_contraction"],
            tightness_ratio=best_result["tightness_ratio"],
            # Sub-scores
            score_box_tightness=sub.get("box_tightness"),
            score_touch_density=sub.get("touch_density"),
            score_oscillation=sub.get("oscillation"),
            score_atr_squeeze=sub.get("atr_squeeze"),
            score_lps_tightness=sub.get("lps_tightness"),
            score_vol_contraction=sub.get("vol_contraction"),
            score_base_age=sub.get("base_age"),
            score_uptrend_bonus=sub.get("uptrend_bonus"),
            score_rs_bonus=sub.get("rs_bonus"),
            score_high_proximity=sub.get("high_proximity"),
            score_breadth_bonus=sub.get("breadth_bonus"),
            # Volume-around-touches signature + LPS shape/zone detail
            r_touch_vol_z=best_result.get("r_touch_vol_z"),
            s_touch_vol_z=best_result.get("s_touch_vol_z"),
            lps_descent_frac=best_result.get("lps_descent_frac"),
            lps_zone_type=best_result.get("lps_zone_type"),
            # VCP contraction footprint
            contraction_count=best_result.get("contraction_count"),
            contraction_quality=best_result.get("contraction_quality"),
            final_contraction_depth=best_result.get("final_contraction_depth"),
            score_contraction=sub.get("contraction"),
            # Ascending-support / higher-lows footprint
            support_slope_atr=best_result.get("support_slope_atr"),
            ascending_support_quality=best_result.get("ascending_support_quality"),
            score_ascending_support=sub.get("ascending_support"),
            # Forward returns
            **fwd_returns,
            # Market context
            spy_trend=market_ctx.get("spy_trend"),
            vix_level=market_ctx.get("vix_level"),
            sector_etf=sector_etf,
            sector_trend=sector_trend,
            dist_52w_high_pct=best_result.get("dist_52w_high_pct"),
            excess_return_6m=best_result.get("excess_return_6m"),
            bars_since_bc=best_result.get("bars_since_BC"),
            descent_length=best_result.get("descent_length"),
            # Seed archive uses find_outer_box exclusively → always outer.
            phase_d_inner=0,
            # Labels
            source="seed",
            quality_label="perfect",
        )

        if existing:
            for k, v in values.items():
                setattr(existing, k, v)
        else:
            session.add(SetupArchive(**values))

        log.info(
            f"  ✓ {ticker} @ {eval_date_str}: {best_result['tier']}-tier "
            f"{best_result['setup_type']} (score={best_result['score']}, "
            f"fwd_20d={fwd_returns.get('fwd_return_20d', 'N/A')})"
        )
        archived += 1

    session.commit()
    session.close()
    log.info(f"\nSeeded {archived}/{len(setups)} setups into the archive.")
    return archived


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed the setup archive with historical winners")
    parser.add_argument("--force", action="store_true", help="Overwrite existing entries")
    args = parser.parse_args()

    seed_archive(force=args.force)

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
from core.archive.forward_returns import FORWARD_RETURN_DOWNLOAD_DAYS, _compute_returns
from core.pipeline.evaluation import (
    _structure_to_boxes,
    apply_baseline_filters,
)
from core.scoring import calculate_tier, score_setup
from core.structure import (
    adr_pct,
    calculate_atr,
    detect_lps,
    detect_lps_tests,
    measure_bar_compression,
    measure_bins,
    measure_contractions,
    measure_equilibrium,
    measure_support_slope,
    measure_traversal,
    trend_template,
)
from core.structure.narrative import read_structure
from core.structure.phase_d import final_v_tip_bar, support_test_evidence_starts

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

    Returns the result dict on pass, or None on reject. Mirrors _evaluate_ticker
    but works on a pre-sliced DataFrame: it reads ONE chronological narrative
    structure (the oldest valid root swing), so there is no box-selection mode.
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
        # Mirror the live chronological reader so seed recall measures the same engine.
        structure = read_structure(df_ind, float(df_ind.iloc[-6]["ATR_10"]))
        if structure is None:
            return None
        boxes = _structure_to_boxes(structure, len(df_ind))
        base_len, res_avg, sup_avg, box_width, r_touches, s_touches, breach_days, \
            r_anchor_bar, s_anchor_bar, bc_anchor_bar, phase_b_start_bar, \
            _is_inner = boxes["parent"]
        inner = boxes["inner"]

        if base_len == 0:
            return None

        atr_eval = df_ind.iloc[-6]
        atr_ratio = atr_eval["ATR_10"] / atr_eval["ATR_50"]

        if latest["Close"] < (sup_avg * settings.CRASH_FILTER_MULT):
            return None
        if latest["Close"] >= (res_avg * settings.EXTENSION_FILTER_MULT):
            return None

        atr_for_zone = float(atr_eval["ATR_10"])

        def _range_threshold(bdf):
            return max(
                float(bdf["Spread"].quantile(settings.LPS_RANGE_PERCENTILE)),
                1.2 * atr_for_zone,
            )

        base_df = df.iloc[-base_len:]
        base_range_threshold = _range_threshold(base_df)

        phase_b_start = len(df_ind) - base_len
        swing_complete_idx = phase_b_start + max(r_anchor_bar, s_anchor_bar)

        lps_in_inner = False
        lps_result = None
        lps_context = (sup_avg, res_avg, base_range_threshold, base_len, swing_complete_idx)
        if inner is not None:
            inner_base_df = df_ind.iloc[-inner["base_len"]:]
            inner_swing_complete = inner["start_bar"] + max(
                inner["r_anchor_bar"], inner["s_anchor_bar"])
            inner_range_threshold = _range_threshold(inner_base_df)
            inner_lps = detect_lps(
                df_ind, latest, inner["S"], inner["R"], atr_for_zone,
                inner_range_threshold, inner["base_len"], inner_swing_complete,
            )
            if inner_lps:
                lps_result = inner_lps
                lps_in_inner = True
                lps_context = (
                    inner["S"], inner["R"], inner_range_threshold,
                    inner["base_len"], inner_swing_complete,
                )
        if lps_result is None:
            lps_result = detect_lps(
                df_ind, latest, sup_avg, res_avg, atr_for_zone,
                base_range_threshold, base_len, swing_complete_idx,
            )

        if not lps_result:
            return None

        setup_state = lps_result["setup_type"]
        is_lps = True
        lps_length = lps_result["length"]
        lps_offset = lps_result["offset"]
        trigger_price = lps_result["trigger_price"]
        vol_contraction = lps_result["vol_contraction"]
        tightness_ratio = lps_result["tightness_ratio"]
        lps_tests = detect_lps_tests(
            df_ind, latest, lps_context[0], lps_context[1],
            atr_for_zone, lps_context[2], lps_context[3], lps_context[4],
        )

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
        bar_compression = measure_bar_compression(base_df, res_avg - sup_avg, atr_for_zone)
        support = measure_support_slope(base_df, atr_for_zone)
        equilibrium = measure_equilibrium(base_df, res_avg, sup_avg, atr_for_zone)
        traversal = measure_traversal(base_df, res_avg, sup_avg, atr_for_zone)
        adr_value = adr_pct(df, settings.ADR_WINDOW)
        adr_quality = (
            min(adr_value / settings.ADR_FULL_PCT, 1.0)
            if settings.ADR_FULL_PCT else 0.0
        )

        phase_d_start_bar = int(inner["start_bar"]) if inner is not None else None
        phase_b_start = len(df_ind) - base_len
        bc_anchor_bar, phase_a_end_bar = int(structure.climax_bar), int(structure.ar_bar)
        phase_d_evidence_starts = (
            {"support_tests": None, "sos_reclaim": None, "rising_support": None}
            if inner is not None
            else support_test_evidence_starts(lps_tests, phase_b_start, base_len)
        )
        support_test_start_bar = phase_d_evidence_starts["support_tests"]
        v_tip_bar = None if inner is not None else final_v_tip_bar(df_ind, phase_b_start, base_len)
        # Region (bin) features + Minervini trend template (measure-first parity
        # with the live pipeline).
        bins = measure_bins(
            df_ind,
            bc_anchor_bar=bc_anchor_bar,
            phase_b_start_bar=phase_b_start_bar,
            base_len=base_len,
            is_inner_box=False,
            lps_offset=lps_offset,
            lps_length=lps_length,
            R=res_avg,
            S=sup_avg,
            atr_val=atr_for_zone,
            phase_d_start_bar=phase_d_start_bar,
            support_test_start_bar=support_test_start_bar,
            sos_reclaim_start_bar=phase_d_evidence_starts["sos_reclaim"],
            rising_support_start_bar=phase_d_evidence_starts["rising_support"],
            phase_a_end_bar=phase_a_end_bar,
            v_tip_bar=v_tip_bar,
            lps_R=lps_context[1],
            lps_S=lps_context[0],
        )
        trend = trend_template(df_ind, dist_52w_high_pct=dist_52w_high_pct)

        score_result = score_setup(
            box_width, r_touches, s_touches, res_avg, sup_avg, base_df,
            atr_ratio, tightness_ratio, vol_contraction, base_len, yearly_return,
            excess_return_6m, dist_52w_high_pct,
            None,  # breadth_pct unknown for historical seed dates
            contraction['quality'], support['quality'], adr_quality,
            traversal_density=(
                traversal['n_full_traversals'] / traversal['n_swings']
                if traversal['n_swings'] else 0.0
            ),
            max_swing_frac=traversal['max_swing_frac'] or 1.0,
            dwell_asymmetry=abs(equilibrium['upper_dwell'] - equilibrium['lower_dwell']),
            has_spring=bool(bins.get('bin_c_present')),
        )
        score = score_result["total"]
        tier = calculate_tier(score, box_width)

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
            "lps_high_descent_frac": float(lps_result.get("high_descent_frac", 1.0)),
            "lps_window_range_pct_box": float(lps_result.get("window_range_pct_box", 0.0)),
            "lps_high_extension_box": float(lps_result.get("high_extension_box", 0.0)),
            "lps_high_extension_atr": float(lps_result.get("high_extension_atr", 0.0)),
            "lps_profile_unit": float(lps_result.get("profile_unit", 0.0)),
            "lps_profile_unit_pct": float(lps_result.get("profile_unit_pct", 0.0)),
            "lps_pullback_profile": float(lps_result.get("pullback_profile", 0.0)),
            "lps_terminal_low_tolerance": float(lps_result.get("terminal_low_tolerance", 0.0)),
            "lps_spread_expansion_profile": float(lps_result.get("spread_expansion_profile", 0.0)),
            "lps_first_high": float(lps_result.get("first_high", 0.0)),
            "lps_last_low": float(lps_result.get("last_low", 0.0)),
            "lps_window_high": float(lps_result.get("window_high", 0.0)),
            "lps_window_low": float(lps_result.get("window_low", 0.0)),
            "lps_zone_type": lps_result.get("zone_type", "INSIDE"),
            "phase_d_inner": bool(inner is not None),
            "lps_in_inner": bool(lps_in_inner),
            "inner_R": float(inner["R"]) if inner is not None else None,
            "inner_S": float(inner["S"]) if inner is not None else None,
            "inner_box_width": float(inner["box_width"]) if inner is not None else None,
            "inner_start_bar": phase_d_start_bar,
            "inner_source": inner.get("source") if inner is not None else None,
            "inner_search_start_bar": (int(inner["search_start_bar"])
                                       if inner is not None else None),
            "inner_climax_bar": (int(inner["climax_bar"])
                                 if inner is not None and inner.get("climax_bar") is not None
                                 else None),
            "inner_reaction_bar": (int(inner["reaction_bar"])
                                   if inner is not None and inner.get("reaction_bar") is not None
                                   else None),
            "inner_reaction_pct": (float(inner["reaction_pct"])
                                   if inner is not None and inner.get("reaction_pct") is not None
                                   else None),
            "inner_reaction_bars": (int(inner["reaction_bars"])
                                    if inner is not None and inner.get("reaction_bars") is not None
                                    else None),
            "contraction_count": int(contraction["n_contractions"]),
            "contraction_quality": float(contraction["quality"]),
            "final_contraction_depth": (float(contraction["final_depth"])
                                        if contraction["final_depth"] is not None else None),
            "contraction_vol_trend": (float(contraction["vol_trend"])
                                      if contraction["vol_trend"] is not None else None),
            "base_median_spread_atr": bar_compression["median_spread_atr"],
            "base_p80_spread_atr": bar_compression["p80_spread_atr"],
            "base_median_spread_pct_box": bar_compression["median_spread_pct_box"],
            "base_tight_bar_pct": float(bar_compression["tight_bar_pct"]),
            "support_slope_atr": (float(support["slope_atr"])
                                  if support["slope_atr"] is not None else None),
            "ascending_support_quality": float(support["quality"]),
            "eq_r_touches": int(equilibrium["r_touches"]),
            "eq_s_touches": int(equilibrium["s_touches"]),
            "eq_r_touch_thirds": int(equilibrium["r_touch_thirds"]),
            "eq_s_touch_thirds": int(equilibrium["s_touch_thirds"]),
            "eq_lower_dwell": float(equilibrium["lower_dwell"]),
            "eq_mid_dwell": float(equilibrium["mid_dwell"]),
            "eq_upper_dwell": float(equilibrium["upper_dwell"]),
            "eq_coverage": float(equilibrium["coverage"]),
            "trav_n_full_traversals": int(traversal["n_full_traversals"]),
            "trav_n_swings": int(traversal["n_swings"]),
            "trav_top_dead_space": (float(traversal["top_dead_space"])
                                    if traversal["top_dead_space"] is not None else None),
            "trav_bottom_dead_space": (float(traversal["bottom_dead_space"])
                                       if traversal["bottom_dead_space"] is not None else None),
            "trav_rail_reaches_high": int(traversal["rail_reaches_high"]),
            "trav_rail_reaches_low": int(traversal["rail_reaches_low"]),
            "trav_max_swing_frac": (float(traversal["max_swing_frac"])
                                    if traversal["max_swing_frac"] is not None else None),
            "trav_last_support_frac": (float(traversal["last_support_frac"])
                                       if traversal["last_support_frac"] is not None else None),
            "trav_coil_floor_pos": (float(traversal["coil_floor_pos"])
                                    if traversal["coil_floor_pos"] is not None else None),
            "adr_pct": float(adr_value),
            "adr_quality": float(adr_quality),
            # Region (bin) features + Minervini trend template (measure-first).
            **bins,
            **trend,
        }

    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError,
            AttributeError):
        # Parity with the live _evaluate_ticker guard: the structure-adapter path
        # can raise AttributeError on a degenerate frame; skip the date, never crash.
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
    dl_end = (latest + pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)).strftime("%Y-%m-%d")

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
            contraction_vol_trend=best_result.get("contraction_vol_trend"),
            score_contraction=sub.get("contraction"),
            # Base bar-compression texture
            base_median_spread_atr=best_result.get("base_median_spread_atr"),
            base_p80_spread_atr=best_result.get("base_p80_spread_atr"),
            base_median_spread_pct_box=best_result.get("base_median_spread_pct_box"),
            base_tight_bar_pct=best_result.get("base_tight_bar_pct"),
            # Ascending-support / higher-lows footprint
            support_slope_atr=best_result.get("support_slope_atr"),
            ascending_support_quality=best_result.get("ascending_support_quality"),
            score_ascending_support=sub.get("ascending_support"),
            # Worked-equilibrium occupancy metrics (raw, measure-first)
            eq_r_touches=best_result.get("eq_r_touches"),
            eq_s_touches=best_result.get("eq_s_touches"),
            eq_r_touch_thirds=best_result.get("eq_r_touch_thirds"),
            eq_s_touch_thirds=best_result.get("eq_s_touch_thirds"),
            eq_lower_dwell=best_result.get("eq_lower_dwell"),
            eq_mid_dwell=best_result.get("eq_mid_dwell"),
            eq_upper_dwell=best_result.get("eq_upper_dwell"),
            eq_coverage=best_result.get("eq_coverage"),
            # Limb-traversal read (raw, measure-first)
            trav_n_full_traversals=best_result.get("trav_n_full_traversals"),
            trav_n_swings=best_result.get("trav_n_swings"),
            trav_top_dead_space=best_result.get("trav_top_dead_space"),
            trav_bottom_dead_space=best_result.get("trav_bottom_dead_space"),
            trav_rail_reaches_high=best_result.get("trav_rail_reaches_high"),
            trav_rail_reaches_low=best_result.get("trav_rail_reaches_low"),
            trav_max_swing_frac=best_result.get("trav_max_swing_frac"),
            trav_last_support_frac=best_result.get("trav_last_support_frac"),
            trav_coil_floor_pos=best_result.get("trav_coil_floor_pos"),
            # ADR% absolute-volatility character
            adr_pct=best_result.get("adr_pct"),
            score_adr=sub.get("adr"),
            # Region (bin) features (A/B/D/LPS size, range, volume + Last Supper)
            bin_a_bars=best_result.get("bin_a_bars"),
            bin_a_range_pct=best_result.get("bin_a_range_pct"),
            bin_a_volume_ratio=best_result.get("bin_a_volume_ratio"),
            bin_b_bars=best_result.get("bin_b_bars"),
            bin_b_range_pct=best_result.get("bin_b_range_pct"),
            bin_b_volume_ratio=best_result.get("bin_b_volume_ratio"),
            bin_b_cog_end=best_result.get("bin_b_cog_end"),
            bin_b_cog_crossings=best_result.get("bin_b_cog_crossings"),
            bin_b_cog_rng=best_result.get("bin_b_cog_rng"),
            bin_b_cog_corr=best_result.get("bin_b_cog_corr"),
            bin_c_present=(int(bool(best_result.get("bin_c_present")))
                           if best_result.get("bin_c_present") is not None else None),
            bin_c_type=best_result.get("bin_c_type"),
            bin_c_event_date=best_result.get("bin_c_event_date"),
            bin_c_event_bar=best_result.get("bin_c_event_bar"),
            bin_c_undercut_atr=best_result.get("bin_c_undercut_atr"),
            bin_c_recovery_bars=best_result.get("bin_c_recovery_bars"),
            bin_c_recovery_bar=best_result.get("bin_c_recovery_bar"),
            bin_c_time_loc=best_result.get("bin_c_time_loc"),
            bin_c_spring_vol_z=best_result.get("bin_c_spring_vol_z"),
            bin_d_bars=best_result.get("bin_d_bars"),
            bin_d_start_bar=best_result.get("bin_d_start_bar"),
            bin_d_range_pct=best_result.get("bin_d_range_pct"),
            bin_d_volume_ratio=best_result.get("bin_d_volume_ratio"),
            bin_d_support_slope_atr=best_result.get("bin_d_support_slope_atr"),
            bin_d_higher_low_frac=best_result.get("bin_d_higher_low_frac"),
            bin_d_ascending_support_quality=best_result.get("bin_d_ascending_support_quality"),
            bin_d_boundary_source=best_result.get("bin_d_boundary_source"),
            phase_d_evidence_json=best_result.get("phase_d_evidence_json"),
            bin_lps_bars=best_result.get("bin_lps_bars"),
            lps_position_in_box=best_result.get("lps_position_in_box"),
            bin_d_vs_b_range_ratio=best_result.get("bin_d_vs_b_range_ratio"),
            bin_d_vs_b_volume_ratio=best_result.get("bin_d_vs_b_volume_ratio"),
            bin_d_vs_b_support_quality_delta=best_result.get("bin_d_vs_b_support_quality_delta"),
            lps_stretch_atr=best_result.get("lps_stretch_atr"),
            lps_stretch_box=best_result.get("lps_stretch_box"),
            # Minervini Stage-2 trend-template context (raw, no scoring)
            stage2_ma_stack_pass=(int(bool(best_result.get("stage2_ma_stack_pass")))
                                  if best_result.get("stage2_ma_stack_pass") is not None else None),
            stage2_ma200_slope_1m_pct=best_result.get("stage2_ma200_slope_1m_pct"),
            stage2_52w_low_pct=best_result.get("stage2_52w_low_pct"),
            stage2_trend_pass_count=best_result.get("stage2_trend_pass_count"),
            stage2_trend_pass=(int(bool(best_result.get("stage2_trend_pass")))
                               if best_result.get("stage2_trend_pass") is not None else None),
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
            phase_d_inner=(int(bool(best_result.get("phase_d_inner")))
                           if best_result.get("phase_d_inner") is not None else None),
            lps_in_inner=(int(bool(best_result.get("lps_in_inner")))
                          if best_result.get("lps_in_inner") is not None else None),
            inner_source=best_result.get("inner_source"),
            inner_search_start_bar=best_result.get("inner_search_start_bar"),
            inner_climax_bar=best_result.get("inner_climax_bar"),
            inner_reaction_bar=best_result.get("inner_reaction_bar"),
            inner_reaction_pct=best_result.get("inner_reaction_pct"),
            inner_reaction_bars=best_result.get("inner_reaction_bars"),
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

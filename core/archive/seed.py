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

import pandas as pd

_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_BACKEND_DIR = os.path.join(_PROJECT_ROOT, "webapp", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.append(_BACKEND_DIR)

from config import settings
from core.archive.forward_returns import FORWARD_RETURN_DOWNLOAD_DAYS, _compute_returns
from core.pipeline.evaluation import _run_eval_chain
from core.archive.result_adapter import seed_row_from_result
from core.pipeline.downloads import _batched_download
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
from core.structure.htf import htf_archive_values

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

# Seed/fresh-recall needs enough lookback for monthly HTF Stage-2 context. The
# daily structure read is trimmed in _evaluate_at_date, so this extra history
# enriches HTF only and does not change the daily root walk.
SEED_HISTORY_DAYS = 365 * 5 + 30


def _ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        try:
            return raw[ticker].dropna()
        except KeyError:
            return pd.DataFrame()
    return raw.dropna()


def _close_series(raw: pd.DataFrame, ticker: str):
    frame = _ticker_frame(raw, ticker)
    if frame.empty or "Close" not in frame:
        return None
    close = frame["Close"]
    return close.iloc[:, 0] if hasattr(close, "columns") else close


def _evaluate_at_date(df: pd.DataFrame, spy_6m_return: float = 0.0) -> Optional[dict]:
    """Evaluate df (last bar = evaluation date) through the SAME numeric chain the
    live screener uses, then re-key the canonical result to the unprefixed shape the
    seed archive writer consumes.

    Delegates to ``core.pipeline.evaluation._run_eval_chain`` so that "replay at T ==
    live at T" holds by construction rather than by a recall test. Seed runs with
    ``breadth_pct=None`` (there is no live universe-breadth at a historical replay
    date), matching the prior behaviour. ``seed_row_from_result`` is the single
    boundary translating the canonical contract to the writer's historical key names.
    """
    try:
        result = _run_eval_chain("", df, spy_6m_return, None)
    except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError,
            AttributeError):
        # Parity with the live _evaluate_ticker guard: skip the date, never crash.
        return None
    return seed_row_from_result(result) if result is not None else None


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

    # Frozen engine-config version stamped on every seeded row (computed once —
    # provenance only, never a computed engine field).
    from core.freeze.manifest import manifest_hash
    engine_config_version = manifest_hash()

    # Batch download all tickers
    unique_tickers = sorted({t for t, _ in setups})
    earliest = min(pd.Timestamp(d) for _, d in setups)
    latest = max(pd.Timestamp(d) for _, d in setups)

    dl_start = (earliest - pd.Timedelta(days=SEED_HISTORY_DAYS)).strftime("%Y-%m-%d")
    dl_end = (latest + pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)).strftime("%Y-%m-%d")

    log.info(f"Downloading {len(unique_tickers)} tickers from {dl_start} -> {dl_end}...")
    raw = _batched_download(
        unique_tickers,
        {"start": dl_start, "end": dl_end, "auto_adjust": True},
        "Seed download",
    )

    # SPY history for per-date RS computation — same window so any seed eval
    # date can look back RS_LOOKBACK_BARS without falling off the start.
    log.info("Downloading SPY for RS reference...")
    spy_raw = _batched_download(
        ["SPY"],
        {"start": dl_start, "end": dl_end, "auto_adjust": True},
        "Seed SPY",
    )
    spy_close_series = _close_series(spy_raw, "SPY")

    # Parse per-ticker DataFrames
    data: dict[str, pd.DataFrame] = {}
    for t in unique_tickers:
        df = _ticker_frame(raw, t)
        if not df.empty:
            data[t] = df

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

        # Check if already exists (by the actual signal date, not trigger date).
        # Seed rows are the hand-picked equities winners gallery, so the existence
        # check must match the widened 3-col identity key (conventions.md EC-4) —
        # otherwise it ignores the universe dimension and could overwrite the wrong
        # row once any non-equities universe is ever seeded.
        existing = session.query(SetupArchive).filter_by(
            ticker=ticker, scan_date=eval_date_str, universe_type=DEFAULT_UNIVERSE_TYPE
        ).first()
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
            universe_type=DEFAULT_UNIVERSE_TYPE,  # equities winners gallery (EC-4)
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
            lps_swing_type=best_result.get("lps_swing_type"),
            lps_anchor_bar=best_result.get("lps_anchor_bar"),
            lps_anchor_date=best_result.get("lps_anchor_date"),
            lps_low_bar=best_result.get("lps_low_bar"),
            lps_low_date=best_result.get("lps_low_date"),
            lps_swing_depth_pct=best_result.get("lps_swing_depth_pct"),
            lps_swing_depth_atr=best_result.get("lps_swing_depth_atr"),
            lps_swing_depth_box=best_result.get("lps_swing_depth_box"),
            last_supper_pullback_from_extension_pct=best_result.get("last_supper_pullback_from_extension_pct"),
            last_supper_source_box_age=best_result.get("last_supper_source_box_age"),
            last_supper_reclaim_quality=best_result.get("last_supper_reclaim_quality"),
            # Minervini Stage-2 trend-template context (raw, no scoring)
            stage2_ma_stack_pass=(int(bool(best_result.get("stage2_ma_stack_pass")))
                                  if best_result.get("stage2_ma_stack_pass") is not None else None),
            stage2_ma200_slope_1m_pct=best_result.get("stage2_ma200_slope_1m_pct"),
            stage2_52w_low_pct=best_result.get("stage2_52w_low_pct"),
            stage2_trend_pass_count=best_result.get("stage2_trend_pass_count"),
            stage2_trend_pass=(int(bool(best_result.get("stage2_trend_pass")))
                               if best_result.get("stage2_trend_pass") is not None else None),
            # HTF (higher-timeframe) context — same engine on weekly/monthly bars
            **htf_archive_values(best_result.get, prefixed=False),
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
            # Engine provenance (frozen-config reproducibility)
            engine_config_version=engine_config_version,
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


def fired_seeds_fresh(
    setups: list[tuple[str, str]] | None = None,
) -> dict[tuple[str, str], Optional[dict]]:
    """Re-evaluate each seed winner with the CURRENT engine on FRESH data,
    WITHOUT writing the archive.

    Downloads the tickers and runs the SAME ``-WINDOW_BACK / +WINDOW_FWD``
    best-by-score scan-back ``seed_archive`` uses, returning
    ``{(ticker, trigger_date): result_dict_or_None}``. This is the read-only
    truth the seed-recall guard's ``--fresh`` mode needs: it measures what the
    live engine fires TODAY rather than what a (possibly stale) archive recorded,
    so engine changes that silently drop winners surface immediately. Bad-data
    seeds (USO/BRZU) are filtered out.
    """
    from core.archive.seed_recall import filter_ignored_seeds

    if setups is None:
        setups = SEED_SETUPS
    active, _ignored = filter_ignored_seeds(setups)
    if not active:
        return {}

    unique = sorted({t for t, _ in active})
    earliest = min(pd.Timestamp(d) for _, d in active)
    latest = max(pd.Timestamp(d) for _, d in active)
    dl_start = (earliest - pd.Timedelta(days=SEED_HISTORY_DAYS)).strftime("%Y-%m-%d")
    dl_end = (latest + pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)).strftime("%Y-%m-%d")

    log.info(f"[fresh recall] downloading {len(unique)} tickers {dl_start} -> {dl_end} ...")
    raw = _batched_download(
        unique,
        {"start": dl_start, "end": dl_end, "auto_adjust": True},
        "Fresh seed recall",
    )
    spy_raw = _batched_download(
        ["SPY"],
        {"start": dl_start, "end": dl_end, "auto_adjust": True},
        "Fresh seed SPY",
    )
    spy_close = _close_series(spy_raw, "SPY")

    data: dict[str, pd.DataFrame] = {}
    for t in unique:
        df = _ticker_frame(raw, t)
        if not df.empty:
            data[t] = df

    def _spy6(eval_date) -> float:
        if spy_close is None:
            return 0.0
        s = spy_close[spy_close.index <= eval_date]
        if len(s) > settings.RS_LOOKBACK_BARS:
            return float(s.iloc[-1] / s.iloc[-settings.RS_LOOKBACK_BARS - 1] - 1.0)
        return 0.0

    out: dict[tuple[str, str], Optional[dict]] = {}
    seen: set[tuple[str, str]] = set()
    for ticker, date_str in active:
        if (ticker, date_str) in seen:
            continue
        seen.add((ticker, date_str))
        df_full = data.get(ticker)
        if df_full is None:
            out[(ticker, date_str)] = None
            continue
        target = pd.Timestamp(date_str)
        best = None
        for offset in range(-WINDOW_BACK, WINDOW_FWD + 1):
            eval_date = target + pd.Timedelta(days=offset)
            df_slice = df_full[df_full.index <= eval_date]
            if len(df_slice) < 200:
                continue
            result = _evaluate_at_date(df_slice, spy_6m_return=_spy6(eval_date))
            if result is not None and (best is None or result["score"] > best["score"]):
                best = result
        out[(ticker, date_str)] = best
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed the setup archive with historical winners")
    parser.add_argument("--force", action="store_true", help="Overwrite existing entries")
    args = parser.parse_args()

    seed_archive(force=args.force)

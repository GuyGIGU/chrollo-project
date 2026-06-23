"""Archive manual-add, analysis, and forward-return action endpoints."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from archive_models import SetupArchive
from database import get_db
from routers.archive_schemas import ManualSetupIn, SetupOut
from services import archive_jobs
from services.db_write import commit_or_http

router = APIRouter(tags=["archive"])

# Three levels up from routers/ reaches the project root, where core/ lives.
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ANALYSIS_LOCK = threading.Lock()
_ANALYSIS_SOURCES = {"screener", "seed", "manual"}


@router.post("/add-setup", response_model=SetupOut)
def add_setup_manually(payload: ManualSetupIn, db: Session = Depends(get_db)):
    """Manually add a setup to the archive.

    Downloads OHLC for the ticker, slices the DataFrame at ``scan_date`` (or
    today), runs the full screener pipeline at that date, and writes the
    resulting row with ``source="manual"``. Forward returns are computed
    immediately from the bars after ``scan_date`` (if any exist yet).

    Raises 422 if the screener doesn't fire on the given date — we want the
    structural fingerprint, so we won't store a "setup" the engine rejected.
    """
    import sys as _sys
    import os as _os
    import pandas as _pd

    # Make project root importable so we can use core/ modules.
    _root = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    from core.archive.seed import SEED_HISTORY_DAYS, _evaluate_at_date
    from core.archive.forward_returns import FORWARD_RETURN_DOWNLOAD_DAYS, _compute_returns
    from core.pipeline.downloads import _batched_download
    from core.structure.htf import htf_archive_values
    from archive_models import (
        SetupArchive,
        get_market_context,
        get_sector_etf,
        get_sector_trend,
    )

    def _download_one(symbol: str, start_date: str, end_date: str, label: str):
        raw_frame = _batched_download(
            [symbol],
            {"start": start_date, "end": end_date, "auto_adjust": True},
            label,
        )
        if raw_frame is None or raw_frame.empty:
            return raw_frame
        if hasattr(raw_frame.columns, "nlevels") and raw_frame.columns.nlevels > 1:
            try:
                return raw_frame[symbol].dropna()
            except KeyError:
                return _pd.DataFrame()
        return raw_frame.dropna()

    ticker = (payload.ticker or "").strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    scan_dt = (payload.scan_date or _pd.Timestamp.today().strftime("%Y-%m-%d")).strip()
    try:
        target_ts = _pd.Timestamp(scan_dt)
    except Exception:
        raise HTTPException(status_code=400, detail=f"invalid scan_date: {scan_dt}")

    existing = (
        db.query(SetupArchive)
        .filter_by(ticker=ticker, scan_date=scan_dt)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"{ticker} @ {scan_dt} already in archive")

    # Download enough history for monthly HTF context; _evaluate_at_date trims
    # the daily structure read back to settings.DAILY_STRUCTURE_PERIOD.
    start = (target_ts - _pd.Timedelta(days=SEED_HISTORY_DAYS)).strftime("%Y-%m-%d")
    end = (target_ts + _pd.Timedelta(days=FORWARD_RETURN_DOWNLOAD_DAYS)).strftime("%Y-%m-%d")
    try:
        raw = _download_one(ticker, start, end, f"Manual archive {ticker}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"market-data download failed: {e}")
    if raw is None or raw.empty:
        raise HTTPException(status_code=404, detail=f"no market data found for {ticker}")
    if hasattr(raw.columns, "nlevels") and raw.columns.nlevels > 1:
        raw.columns = raw.columns.droplevel("Ticker")

    df_slice = raw[raw.index <= target_ts].dropna()
    if len(df_slice) < 200:
        raise HTTPException(status_code=422, detail=f"only {len(df_slice)} bars at {scan_dt} (need 200+)")

    result = _evaluate_at_date(df_slice)
    if result is None:
        raise HTTPException(
            status_code=422,
            detail=f"screener did not fire on {ticker} @ {scan_dt} — no valid LPS at that date",
        )

    fwd_df = raw[raw.index > target_ts]
    hist_df = raw[raw.index <= target_ts]
    vol_50_at_scan = None
    if "Volume" in hist_df.columns and len(hist_df) >= 50:
        vs = hist_df["Volume"]
        if hasattr(vs, "columns"):
            vs = vs.iloc[:, 0]
        vol_50_at_scan = float(vs.tail(50).mean())
    fwd_returns = (
        _compute_returns(
            fwd_df, result["current_price"], result["trigger_price"],
            s_level=result.get("s_level"), vol_50_at_scan=vol_50_at_scan,
        )
        if not fwd_df.empty else {}
    )

    market_ctx = get_market_context(scan_dt)
    sector_etf = get_sector_etf(ticker)
    sector_trend = get_sector_trend(sector_etf, scan_dt) if sector_etf else None
    sub = result.get("sub_scores", {}) or {}

    # RS vs sector: stock base return − sector ETF base return, same window.
    rs_vs_sector = None
    base_start = result.get("base_date_start"); base_end = result.get("base_date_end")
    if sector_etf and base_start and base_end:
        try:
            sec_raw = _download_one(sector_etf, base_start, base_end, f"Manual archive {sector_etf}")
            if sec_raw is not None and not sec_raw.empty:
                sc = sec_raw["Close"]
                if hasattr(sc, "columns"): sc = sc.iloc[:, 0]
                if len(sc) >= 2:
                    sec_ret = (float(sc.iloc[-1]) - float(sc.iloc[0])) / float(sc.iloc[0])
                    bcs = float(result.get("base_close_start") or 0)
                    bce = float(result.get("base_close_end") or 0)
                    if bcs > 0:
                        stock_ret = (bce - bcs) / bcs
                        rs_vs_sector = round(stock_ret - sec_ret, 5)
        except Exception:
            rs_vs_sector = None

    row = SetupArchive(
        ticker=ticker,
        scan_date=scan_dt,
        setup_type=result["setup_type"],
        tier=result["tier"],
        score=result["score"],
        current_price=result["current_price"],
        r_level=result["r_level"],
        s_level=result["s_level"],
        trigger_price=result["trigger_price"],
        base_length=result["base_length"],
        box_width=result["box_width"],
        touches=result["touches"],
        r_touches=result["r_touches"],
        s_touches=result["s_touches"],
        r_anchor=result.get("r_anchor"),
        s_anchor=result.get("s_anchor"),
        atr_ratio=result["atr_ratio"],
        lps_length=result["lps_length"],
        breach_days=result["breach_days"],
        vol_contraction=result["vol_contraction"],
        tightness_ratio=result["tightness_ratio"],
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
        score_contraction=sub.get("contraction"),
        score_ascending_support=sub.get("ascending_support"),
        adr_pct=result.get("adr_pct"),
        score_adr=sub.get("adr"),
        base_median_spread_atr=result.get("base_median_spread_atr"),
        base_p80_spread_atr=result.get("base_p80_spread_atr"),
        base_median_spread_pct_box=result.get("base_median_spread_pct_box"),
        base_tight_bar_pct=result.get("base_tight_bar_pct"),
        r_touch_vol_z=result.get("r_touch_vol_z"),
        s_touch_vol_z=result.get("s_touch_vol_z"),
        lps_descent_frac=result.get("lps_descent_frac"),
        lps_zone_type=result.get("lps_zone_type"),
        contraction_count=result.get("contraction_count"),
        contraction_quality=result.get("contraction_quality"),
        final_contraction_depth=result.get("final_contraction_depth"),
        contraction_vol_trend=result.get("contraction_vol_trend"),
        support_slope_atr=result.get("support_slope_atr"),
        ascending_support_quality=result.get("ascending_support_quality"),
        eq_r_touches=result.get("eq_r_touches"),
        eq_s_touches=result.get("eq_s_touches"),
        eq_r_touch_thirds=result.get("eq_r_touch_thirds"),
        eq_s_touch_thirds=result.get("eq_s_touch_thirds"),
        eq_lower_dwell=result.get("eq_lower_dwell"),
        eq_mid_dwell=result.get("eq_mid_dwell"),
        eq_upper_dwell=result.get("eq_upper_dwell"),
        eq_coverage=result.get("eq_coverage"),
        # Limb-traversal read — mirror the live writer / seed so manual rows are
        # structurally complete for analyze.py (otherwise these read as NULL).
        trav_n_full_traversals=result.get("trav_n_full_traversals"),
        trav_n_swings=result.get("trav_n_swings"),
        trav_top_dead_space=result.get("trav_top_dead_space"),
        trav_bottom_dead_space=result.get("trav_bottom_dead_space"),
        trav_rail_reaches_high=result.get("trav_rail_reaches_high"),
        trav_rail_reaches_low=result.get("trav_rail_reaches_low"),
        trav_max_swing_frac=result.get("trav_max_swing_frac"),
        bin_a_bars=result.get("bin_a_bars"),
        bin_a_range_pct=result.get("bin_a_range_pct"),
        bin_a_volume_ratio=result.get("bin_a_volume_ratio"),
        bin_b_bars=result.get("bin_b_bars"),
        bin_b_range_pct=result.get("bin_b_range_pct"),
        bin_b_volume_ratio=result.get("bin_b_volume_ratio"),
        bin_b_cog_end=result.get("bin_b_cog_end"),
        bin_b_cog_crossings=result.get("bin_b_cog_crossings"),
        bin_b_cog_rng=result.get("bin_b_cog_rng"),
        bin_b_cog_corr=result.get("bin_b_cog_corr"),
        bin_c_present=(int(bool(result.get("bin_c_present")))
                       if result.get("bin_c_present") is not None else None),
        bin_c_type=result.get("bin_c_type"),
        bin_c_event_date=result.get("bin_c_event_date"),
        bin_c_event_bar=result.get("bin_c_event_bar"),
        bin_c_undercut_atr=result.get("bin_c_undercut_atr"),
        bin_c_recovery_bars=result.get("bin_c_recovery_bars"),
        bin_c_recovery_bar=result.get("bin_c_recovery_bar"),
        bin_c_time_loc=result.get("bin_c_time_loc"),
        bin_c_spring_vol_z=result.get("bin_c_spring_vol_z"),
        bin_d_bars=result.get("bin_d_bars"),
        bin_d_start_bar=result.get("bin_d_start_bar"),
        bin_d_range_pct=result.get("bin_d_range_pct"),
        bin_d_volume_ratio=result.get("bin_d_volume_ratio"),
        bin_d_support_slope_atr=result.get("bin_d_support_slope_atr"),
        bin_d_higher_low_frac=result.get("bin_d_higher_low_frac"),
        bin_d_ascending_support_quality=result.get("bin_d_ascending_support_quality"),
        bin_d_boundary_source=result.get("bin_d_boundary_source"),
        phase_d_evidence_json=result.get("phase_d_evidence_json"),
        bin_lps_bars=result.get("bin_lps_bars"),
        lps_position_in_box=result.get("lps_position_in_box"),
        bin_d_vs_b_range_ratio=result.get("bin_d_vs_b_range_ratio"),
        bin_d_vs_b_volume_ratio=result.get("bin_d_vs_b_volume_ratio"),
        bin_d_vs_b_support_quality_delta=result.get("bin_d_vs_b_support_quality_delta"),
        lps_stretch_atr=result.get("lps_stretch_atr"),
        lps_stretch_box=result.get("lps_stretch_box"),
        spy_trend=market_ctx.get("spy_trend"),
        vix_level=market_ctx.get("vix_level"),
        sector_etf=sector_etf,
        sector_trend=sector_trend,
        rs_vs_sector_pct=rs_vs_sector,
        dist_52w_high_pct=result.get("dist_52w_high_pct"),
        phase_d_inner=(int(bool(result.get("phase_d_inner")))
                       if result.get("phase_d_inner") is not None else None),
        lps_in_inner=(int(bool(result.get("lps_in_inner")))
                      if result.get("lps_in_inner") is not None else None),
        inner_source=result.get("inner_source"),
        inner_search_start_bar=result.get("inner_search_start_bar"),
        inner_climax_bar=result.get("inner_climax_bar"),
        inner_reaction_bar=result.get("inner_reaction_bar"),
        inner_reaction_pct=result.get("inner_reaction_pct"),
        inner_reaction_bars=result.get("inner_reaction_bars"),
        **htf_archive_values(result.get, prefixed=False),
        source="manual",
        quality_label=payload.quality_label,
        notes=payload.notes,
        **fwd_returns,
    )
    db.add(row)
    commit_or_http(db, conflict_detail=f"{ticker} @ {scan_dt} already in archive")
    db.refresh(row)
    return row


_ANALYSIS_CACHE: Dict[str, Any] = {"report": None, "ts": 0.0}


@router.get("/analysis")
def get_archive_analysis(
    source: Optional[str] = Query(None, description="Restrict to a source: screener / seed / manual"),
    refresh: bool = Query(False, description="Bypass the ~5min cache and re-run"),
):
    """Run the read-only archive analysis report (mirrors ``python -m core.archive.analyze``)
    and return it as text. Cached ~5 minutes per process unless ``refresh=true``."""
    import time as _time

    if source is not None and source not in _ANALYSIS_SOURCES:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

    now = _time.time()
    if (
        not refresh
        and not source
        and _ANALYSIS_CACHE["report"] is not None
        and (now - _ANALYSIS_CACHE["ts"] < 300)
    ):
        return {"report": _ANALYSIS_CACHE["report"], "cached": True}

    if not _ANALYSIS_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Archive analysis is already running")

    cmd = [sys.executable, "-m", "core.archive.analyze"]
    if source:
        cmd += ["--source", source]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        try:
            result = subprocess.run(
                cmd,
                cwd=_ROOT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                creationflags=flags,
                env=env,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    finally:
        _ANALYSIS_LOCK.release()

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=(result.stderr or "analysis failed")[-1000:])

    report = result.stdout or ""
    if not source:
        _ANALYSIS_CACHE.update({"report": report, "ts": now})
    return {"report": report, "cached": False}


@router.post("/update-returns")
def trigger_update_returns():
    """Trigger forward return computation for all pending setups."""
    return archive_jobs.start_forward_returns_job()


@router.get("/update-returns/status")
def update_returns_status():
    """Return the latest forward-return maintenance job status."""
    return archive_jobs.get_job_status("forward_returns")

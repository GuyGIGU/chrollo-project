"""Archive manual-add, analysis, and forward-return action endpoints."""
from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from archive_models import SetupArchive
from database import get_db
from routers.archive_schemas import ManualSetupIn, SetupOut

router = APIRouter(tags=["archive"])

# Three levels up from routers/ reaches the project root, where core/ lives.
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


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
    import yfinance as _yf

    # Make project root importable so we can use core/ modules.
    _root = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), "..", "..", ".."))
    if _root not in _sys.path:
        _sys.path.insert(0, _root)

    from core.archive.seed import _evaluate_at_date
    from core.archive.forward_returns import _compute_returns
    from archive_models import (
        SetupArchive,
        get_market_context,
        get_sector_etf,
        get_sector_trend,
    )

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

    # Download enough history for baseline (2y minus a buffer is plenty) plus
    # forward bars for return computation.
    start = (target_ts - _pd.Timedelta(days=365 * 2 + 30)).strftime("%Y-%m-%d")
    end = (target_ts + _pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        raw = _yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"yfinance download failed: {e}")
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
            sec_raw = _yf.download(sector_etf, start=base_start, end=base_end,
                                   progress=False, timeout=20, auto_adjust=True)
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
        score_oscillation=sub.get("oscillation"),
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
        support_slope_atr=result.get("support_slope_atr"),
        ascending_support_quality=result.get("ascending_support_quality"),
        spy_trend=market_ctx.get("spy_trend"),
        vix_level=market_ctx.get("vix_level"),
        sector_etf=sector_etf,
        sector_trend=sector_trend,
        rs_vs_sector_pct=rs_vs_sector,
        dist_52w_high_pct=result.get("dist_52w_high_pct"),
        # Manual-add path runs find_outer_box (via _evaluate_at_date) → always outer.
        phase_d_inner=0,
        source="manual",
        quality_label=payload.quality_label,
        notes=payload.notes,
        **fwd_returns,
    )
    db.add(row)
    db.commit()
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

    now = _time.time()
    if (
        not refresh
        and not source
        and _ANALYSIS_CACHE["report"] is not None
        and (now - _ANALYSIS_CACHE["ts"] < 300)
    ):
        return {"report": _ANALYSIS_CACHE["report"], "cached": True}

    cmd = [sys.executable, "-m", "core.archive.analyze"]
    if source:
        cmd += ["--source", source]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
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

    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=(result.stderr or "analysis failed")[-1000:])

    report = result.stdout or ""
    if not source:
        _ANALYSIS_CACHE.update({"report": report, "ts": now})
    return {"report": report, "cached": False}


@router.post("/update-returns")
def trigger_update_returns():
    """Trigger forward return computation for all pending setups."""
    try:
        script = os.path.join(_ROOT_DIR, "core", "archive", "forward_returns.py")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(
            [sys.executable, script],
            cwd=_ROOT_DIR,
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=flags,
        )
        return {
            "status": "ok",
            "stdout": result.stdout[-2000:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
            "returncode": result.returncode,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

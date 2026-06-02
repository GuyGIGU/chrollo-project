"""
Archive API — endpoints for browsing, analyzing, and calibrating the setup archive.

Provides:
  - CRUD for archived setups (list, detail, label, notes)
  - Aggregate calibration analytics (tier performance, sub-score correlations)
  - Manual trigger for forward return updates
"""
from __future__ import annotations

import subprocess
import sys
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from archive_models import SetupArchive
from database import get_db

router = APIRouter(prefix="/archive", tags=["archive"])

# This file lives at webapp/backend/routers/archive.py — three levels up
# from `routers/` (routers → backend → webapp → project root) is where
# run_screener.py and core/ live. Two levels only reached webapp/, which is
# why the subprocess looked for webapp/core/update_forward_returns.py.
_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


# ── Schemas ──────────────────────────────────────────────────────

class SetupOut(BaseModel):
    id: int
    ticker: str
    scan_date: str
    setup_type: str
    tier: str
    score: float
    current_price: Optional[float] = None
    r_level: Optional[float] = None
    s_level: Optional[float] = None
    trigger_price: Optional[float] = None
    base_length: Optional[int] = None
    box_width: Optional[float] = None
    touches: Optional[int] = None
    r_touches: Optional[int] = None
    s_touches: Optional[int] = None
    r_anchor: Optional[int] = None
    s_anchor: Optional[int] = None
    atr_ratio: Optional[float] = None
    lps_length: Optional[int] = None
    breach_days: Optional[int] = None
    vol_contraction: Optional[float] = None
    tightness_ratio: Optional[float] = None
    # Sub-scores
    score_box_tightness: Optional[float] = None
    score_touch_density: Optional[float] = None
    score_oscillation: Optional[float] = None
    score_atr_squeeze: Optional[float] = None
    score_lps_tightness: Optional[float] = None
    score_vol_contraction: Optional[float] = None
    score_base_age: Optional[float] = None
    score_uptrend_bonus: Optional[float] = None
    # Forward returns
    triggered: Optional[int] = None
    trigger_date: Optional[str] = None
    fwd_return_1d: Optional[float] = None
    fwd_return_5d: Optional[float] = None
    fwd_return_10d: Optional[float] = None
    fwd_return_20d: Optional[float] = None
    fwd_return_60d: Optional[float] = None
    mfe_20d: Optional[float] = None
    mae_20d: Optional[float] = None
    mfe_60d: Optional[float] = None
    mae_60d: Optional[float] = None
    mfe_20d_date: Optional[str] = None
    mae_20d_date: Optional[str] = None
    r_multiple_20d: Optional[float] = None
    r_multiple_60d: Optional[float] = None
    trigger_volume_ratio: Optional[float] = None
    # Market context
    spy_trend: Optional[str] = None
    vix_level: Optional[float] = None
    sector_etf: Optional[str] = None
    sector_trend: Optional[str] = None
    rs_vs_sector_pct: Optional[float] = None
    dist_52w_high_pct: Optional[float] = None
    # Phase A structural detail
    phase_d_inner: Optional[int] = None
    # Volume-around-touches signature
    r_touch_vol_z: Optional[float] = None
    s_touch_vol_z: Optional[float] = None
    # LPS shape & zone detail
    lps_descent_frac: Optional[float] = None
    lps_zone_type: Optional[str] = None
    # New sub-scores
    score_high_proximity: Optional[float] = None
    score_breadth_bonus: Optional[float] = None
    score_rs_bonus: Optional[float] = None
    # VCP contraction footprint
    contraction_count: Optional[int] = None
    contraction_quality: Optional[float] = None
    final_contraction_depth: Optional[float] = None
    score_contraction: Optional[float] = None
    # Ascending support / higher-lows footprint
    support_slope_atr: Optional[float] = None
    ascending_support_quality: Optional[float] = None
    score_ascending_support: Optional[float] = None
    # ADR% absolute-volatility character
    adr_pct: Optional[float] = None
    score_adr: Optional[float] = None
    # Curation
    quality_label: Optional[str] = None
    notes: Optional[str] = None
    source: Optional[str] = None

    model_config = {"from_attributes": True}


class LabelUpdate(BaseModel):
    quality_label: Optional[str] = None
    notes: Optional[str] = None


class ManualSetupIn(BaseModel):
    ticker: str
    scan_date: Optional[str] = None    # YYYY-MM-DD; defaults to today
    quality_label: Optional[str] = None
    notes: Optional[str] = None


# ── List / Detail ────────────────────────────────────────────────

@router.get("/setups", response_model=List[SetupOut])
def list_setups(
    skip: int = 0,
    limit: int = 200,
    tier: Optional[str] = Query(None),
    setup_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    quality_label: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    sort_by: str = Query("scan_date"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """List archived setups with filtering and sorting."""
    q = db.query(SetupArchive)

    if tier:
        q = q.filter(SetupArchive.tier == tier.upper())
    if setup_type:
        q = q.filter(SetupArchive.setup_type == setup_type.upper())
    if source:
        sources = [s.strip() for s in source.split(",") if s.strip()]
        if len(sources) == 1:
            q = q.filter(SetupArchive.source == sources[0])
        elif sources:
            q = q.filter(SetupArchive.source.in_(sources))
    if quality_label:
        q = q.filter(SetupArchive.quality_label == quality_label)
    if min_score is not None:
        q = q.filter(SetupArchive.score >= min_score)
    if date_from:
        q = q.filter(SetupArchive.scan_date >= date_from)
    if date_to:
        q = q.filter(SetupArchive.scan_date <= date_to)

    # Sorting
    sort_col = getattr(SetupArchive, sort_by, SetupArchive.scan_date)
    if sort_dir == "asc":
        q = q.order_by(sort_col)
    else:
        q = q.order_by(desc(sort_col))

    return q.offset(skip).limit(limit).all()


@router.get("/setups/{setup_id}", response_model=SetupOut)
def get_setup(setup_id: int, db: Session = Depends(get_db)):
    """Get a single archived setup by ID."""
    setup = db.query(SetupArchive).filter(SetupArchive.id == setup_id).first()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")
    return setup


@router.get("/setups/{setup_id}/chart")
def get_setup_chart(setup_id: int, db: Session = Depends(get_db)):
    """Fetch historical data for a specific setup and format it for ScreenerModal."""
    setup = db.query(SetupArchive).filter(SetupArchive.id == setup_id).first()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")

    import yfinance as yf
    import pandas as pd

    target_date = pd.Timestamp(setup.scan_date)
    start_date = (target_date - pd.Timedelta(days=500)).strftime('%Y-%m-%d')
    end_date = (target_date + pd.Timedelta(days=45)).strftime('%Y-%m-%d')

    raw = yf.download(setup.ticker, start=start_date, end=end_date, progress=False, auto_adjust=True)
    if raw.empty:
        raise HTTPException(status_code=404, detail="Market data not found for ticker")

    if raw.columns.nlevels > 1:
        raw.columns = raw.columns.droplevel('Ticker')

    # Re-scale stored R/S/trigger onto the freshly-adjusted candle scale.
    ratio = _adjustment_ratio(raw, target_date, setup.current_price)

    candles = []
    volumes = []
    forward_bars = 0

    for dt, row in raw.iterrows():
        dt_str = dt.strftime('%Y-%m-%d')
        if dt > target_date:
            forward_bars += 1
            
        o = float(row['Open'])
        h = float(row['High'])
        l = float(row['Low'])
        c = float(row['Close'])
        v = int(row['Volume'])
        candles.append({"time": dt_str, "open": o, "high": h, "low": l, "close": c})
        color = 'rgba(38, 166, 154, 0.5)' if c >= o else 'rgba(239, 83, 80, 0.5)'
        volumes.append({"time": dt_str, "value": v, "color": color})

    return {
        "candles": candles,
        "volumes": volumes,
        "base_len": setup.base_length or 0,
        "R": (setup.r_level * ratio) if setup.r_level else setup.r_level,
        "S": (setup.s_level * ratio) if setup.s_level else setup.s_level,
        "lps_len": setup.lps_length or 0,
        "lps_offset": 0,
        "r_anchor": setup.r_anchor,
        "s_anchor": setup.s_anchor,
        "tier": setup.tier,
        "setup": setup.setup_type,
        "score": setup.score,
        "forward_bars": forward_bars,
        "annotations": _build_annotations(setup, ratio),
    }


def _adjustment_ratio(raw, scan_date_ts, stored_close) -> float:
    """Recover the split/dividend adjustment factor between scan-time and now.

    yfinance `auto_adjust=True` rescales the ENTIRE price series for any split
    or dividend that has occurred up to the download date. The R/S levels in
    the archive were computed on the scan-time scale, so whenever an adjustment
    happened between scan_date and today, the freshly-downloaded candles sit on
    a different scale and the stored R/S float away from the structure.

    We recover the multiplicative factor by comparing the stored scan-date
    close (`current_price`) against the freshly-fetched close on the same bar,
    then callers scale R/S/trigger by it so the overlays land back on the base.

    Returns 1.0 when the ratio can't be trusted (missing data, absurd value).
    """
    if not stored_close or stored_close <= 0:
        return 1.0
    try:
        on_or_before = raw[raw.index <= scan_date_ts]
        if on_or_before.empty:
            return 1.0
        fetched_close = float(on_or_before.iloc[-1]["Close"])
        if fetched_close <= 0:
            return 1.0
        ratio = fetched_close / float(stored_close)
        # Sanity band — reject garbage ratios from bad data rows.
        if 0.01 <= ratio <= 100.0:
            return ratio
    except Exception:
        pass
    return 1.0


def _build_annotations(setup, ratio: float = 1.0) -> Dict[str, Any]:
    """Per-setup overlay metadata for the chart: trigger price, MFE/MAE markers.

    `ratio` rescales the price-space trigger line onto the freshly-adjusted
    candle scale (see _adjustment_ratio). MFE/MAE are percentages → scale-free.
    """
    trig = setup.trigger_price
    return {
        "trigger_price": (trig * ratio) if trig else trig,
        "trigger_date": setup.trigger_date,
        "mfe_20d_date": setup.mfe_20d_date,
        "mfe_20d": setup.mfe_20d,
        "mae_20d_date": setup.mae_20d_date,
        "mae_20d": setup.mae_20d,
        "scan_close": (setup.current_price * ratio) if setup.current_price else setup.current_price,
    }


class ChartBatchIn(BaseModel):
    ids: List[int]


@router.post("/charts/batch")
def get_setup_charts_batch(payload: ChartBatchIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Fetch chart data for many setups in one call.

    Groups by ticker so we do one yfinance download per unique ticker (covering
    the union of date ranges across that ticker's setups), then slices per
    setup. Critical for the grid view — calling /chart per card would be
    hundreds of network round trips.

    Returns ``{<setup_id_str>: {candles, volumes, R, S, base_len, lps_len,
    lps_offset, r_anchor, s_anchor, tier, setup, score, forward_bars}}``.
    Missing IDs / failed downloads are silently omitted from the response.
    """
    if not payload.ids:
        return {}

    import pandas as pd
    import yfinance as yf

    setups = db.query(SetupArchive).filter(SetupArchive.id.in_(payload.ids)).all()
    if not setups:
        return {}

    # Group by ticker, compute the union date window per ticker.
    by_ticker: Dict[str, List[SetupArchive]] = defaultdict(list)
    for s in setups:
        by_ticker[s.ticker].append(s)

    out: Dict[str, Any] = {}
    for ticker, group in by_ticker.items():
        try:
            min_dt = min(pd.Timestamp(s.scan_date) for s in group)
            max_dt = max(pd.Timestamp(s.scan_date) for s in group)
            start = (min_dt - pd.Timedelta(days=500)).strftime("%Y-%m-%d")
            end = (max_dt + pd.Timedelta(days=45)).strftime("%Y-%m-%d")
            raw = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True, timeout=30)
            if raw is None or raw.empty:
                continue
            if hasattr(raw.columns, "nlevels") and raw.columns.nlevels > 1:
                raw.columns = raw.columns.droplevel("Ticker")
        except Exception:
            continue

        for s in group:
            try:
                target = pd.Timestamp(s.scan_date)
                # Re-scale stored R/S/trigger onto the freshly-adjusted candle
                # scale (computed against the full ticker download `raw`, which
                # always contains the scan_date bar).
                ratio = _adjustment_ratio(raw, target, s.current_price)
                # Window: 500 cal days back through scan_date + 45 cal days forward
                lo = target - pd.Timedelta(days=500)
                hi = target + pd.Timedelta(days=45)
                window = raw[(raw.index >= lo) & (raw.index <= hi)]
                if window.empty:
                    continue

                candles, volumes, forward_bars = [], [], 0
                for dt, row in window.iterrows():
                    dt_str = dt.strftime("%Y-%m-%d")
                    if dt > target:
                        forward_bars += 1
                    o = float(row["Open"]); h = float(row["High"])
                    l = float(row["Low"]); c = float(row["Close"])
                    v = int(row["Volume"])
                    candles.append({"time": dt_str, "open": o, "high": h, "low": l, "close": c})
                    color = "rgba(38, 166, 154, 0.5)" if c >= o else "rgba(239, 83, 80, 0.5)"
                    volumes.append({"time": dt_str, "value": v, "color": color})

                out[str(s.id)] = {
                    "candles": candles,
                    "volumes": volumes,
                    "base_len": s.base_length or 0,
                    "R": (s.r_level * ratio) if s.r_level else s.r_level,
                    "S": (s.s_level * ratio) if s.s_level else s.s_level,
                    "lps_len": s.lps_length or 0,
                    "lps_offset": 0,
                    "r_anchor": s.r_anchor,
                    "s_anchor": s.s_anchor,
                    "tier": s.tier,
                    "setup": s.setup_type,
                    "score": s.score,
                    "forward_bars": forward_bars,
                    "annotations": _build_annotations(s, ratio),
                }
            except Exception:
                continue

    return out


@router.get("/setups/{setup_id}/linked-trades")
def linked_trades(
    setup_id: int,
    window_days: int = Query(7, ge=0, le=30),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Find trade_logs entries on the same ticker within ±window_days of
    scan_date — i.e. real positions that were probably triggered by this setup.

    Returns a small projection (id, opening_date, direction, entry/stop/exit,
    pnl, source) so the modal can render a 'Trades on this setup' panel.
    """
    setup = db.query(SetupArchive).filter(SetupArchive.id == setup_id).first()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")

    import pandas as pd
    from models import TradeLog
    try:
        anchor = pd.Timestamp(setup.scan_date)
    except Exception:
        return []
    lo = (anchor - pd.Timedelta(days=window_days)).strftime("%Y-%m-%d")
    hi = (anchor + pd.Timedelta(days=window_days)).strftime("%Y-%m-%d")

    rows = (
        db.query(TradeLog)
        .filter(TradeLog.ticker == setup.ticker)
        .filter(TradeLog.opening_date >= lo)
        .filter(TradeLog.opening_date <= hi)
        .all()
    )
    return [
        {
            "id": t.id,
            "opening_date": t.opening_date,
            "closing_date": t.closing_date,
            "direction": t.direction,
            "entry_price": t.entry_price,
            "stop_loss": t.stop_loss,
            "exit_price": t.exit_price,
            "pnl": t.pnl,
            "source": t.source,
        }
        for t in rows
    ]


@router.patch("/setups/{setup_id}/label")
def update_label(setup_id: int, payload: LabelUpdate, db: Session = Depends(get_db)):
    """Update quality label and/or notes for a setup."""
    setup = db.query(SetupArchive).filter(SetupArchive.id == setup_id).first()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")

    if payload.quality_label is not None:
        setup.quality_label = payload.quality_label
    if payload.notes is not None:
        setup.notes = payload.notes

    db.commit()
    db.refresh(setup)
    return {"status": "ok", "id": setup.id, "quality_label": setup.quality_label}


# ── Stats & Calibration ─────────────────────────────────────────

def _safe_mean(vals: list[float]) -> float:
    return round(float(np.mean(vals)), 5) if vals else 0.0


def _safe_corr(xs: list[float], ys: list[float]) -> float:
    """Pearson correlation, NaN-safe."""
    if len(xs) < 5 or len(ys) < 5:
        return 0.0
    xs_arr = np.array(xs)
    ys_arr = np.array(ys)
    mask = ~(np.isnan(xs_arr) | np.isnan(ys_arr))
    if mask.sum() < 5:
        return 0.0
    corr = float(np.corrcoef(xs_arr[mask], ys_arr[mask])[0, 1])
    # corrcoef returns NaN when either series has zero variance (e.g. a sub-score
    # that's constant across every archived setup). NaN isn't caught by the
    # downstream `x or 0.0` idiom (NaN is truthy), so it poisons the weight
    # normalization and turns every suggested weight into null. Neutralize here.
    return round(corr, 4) if not np.isnan(corr) else 0.0


@router.get("/stats")
def archive_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Aggregate statistics for the archive."""
    setups = db.query(SetupArchive).all()
    total = len(setups)
    with_returns = [s for s in setups if s.fwd_return_20d is not None]

    return {
        "total_setups": total,
        "with_forward_returns": len(with_returns),
        "by_tier": _count_by(setups, "tier"),
        "by_setup_type": _count_by(setups, "setup_type"),
        "by_source": _count_by(setups, "source"),
        "by_quality": _count_by(setups, "quality_label"),
        "date_range": {
            "earliest": min((s.scan_date for s in setups), default=None),
            "latest": max((s.scan_date for s in setups), default=None),
        },
    }


def _count_by(setups: list, field: str) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for s in setups:
        val = getattr(s, field, None) or "unknown"
        counts[val] += 1
    return dict(counts)


@router.get("/calibration")
def calibration_data(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Calibration analytics — the engine for refining the screener.

    Returns tier performance, sub-score correlations with forward returns,
    and setup type breakdown.
    """
    setups = db.query(SetupArchive).all()
    with_returns = [s for s in setups if s.fwd_return_20d is not None]

    # ── Tier Performance ─────────────────────────────────────
    tier_perf: Dict[str, Dict[str, Any]] = {}
    tier_groups: Dict[str, list] = defaultdict(list)
    for s in with_returns:
        tier_groups[s.tier].append(s)

    for tier, group in sorted(tier_groups.items()):
        returns = [s.fwd_return_20d for s in group if s.fwd_return_20d is not None]
        triggered = [s for s in group if s.triggered == 1]
        mfes = [s.mfe_20d for s in group if s.mfe_20d is not None]
        maes = [s.mae_20d for s in group if s.mae_20d is not None]
        r_mults = [s.r_multiple_20d for s in group if s.r_multiple_20d is not None]

        # Expectancy in R-multiples — single number that says
        # "this tier makes/loses N R per setup on average". The headline metric.
        wins = [r for r in r_mults if r > 0]
        losses = [r for r in r_mults if r <= 0]
        wr = (len(wins) / len(r_mults)) if r_mults else 0
        avg_win = float(np.mean(wins)) if wins else 0.0
        avg_loss = float(np.mean(losses)) if losses else 0.0   # negative
        expectancy_r = round(wr * avg_win + (1 - wr) * avg_loss, 3) if r_mults else None

        tier_perf[tier] = {
            "count": len(group),
            "avg_fwd_20d": _safe_mean(returns),
            "win_rate": round(len([r for r in returns if r > 0]) / max(len(returns), 1), 3),
            "trigger_rate": round(len(triggered) / max(len(group), 1), 3),
            "avg_mfe_20d": _safe_mean(mfes),
            "avg_mae_20d": _safe_mean(maes),
            "avg_score": _safe_mean([s.score for s in group]),
            "avg_r_multiple_20d": round(float(np.mean(r_mults)), 3) if r_mults else None,
            "expectancy_r": expectancy_r,
            "r_sample_size": len(r_mults),
        }

    # ── Sub-Score Correlations (20d + 60d) ──────────────────
    # Two horizons are reported side-by-side: 20d ≈ swing-exit window,
    # 60d ≈ position-exit window. A sub-score that predicts well at one
    # horizon but not the other is useful information for re-weighting —
    # if base_age correlates strongly at 60d but weakly at 20d, that's a
    # "long-hold edge" signal, not a swing edge.
    sub_score_fields = [
        "score_box_tightness", "score_touch_density", "score_oscillation",
        "score_atr_squeeze", "score_lps_tightness", "score_vol_contraction",
        "score_base_age",
    ]
    with_60d = [s for s in with_returns if s.fwd_return_60d is not None]
    fwd_20d_vals = [s.fwd_return_20d for s in with_returns]
    fwd_60d_vals = [s.fwd_return_60d for s in with_60d]

    sub_score_corr_20d: Dict[str, float] = {}
    sub_score_corr_60d: Dict[str, float] = {}
    for field in sub_score_fields:
        short_name = field.replace("score_", "")
        vals_20 = [getattr(s, field) or 0.0 for s in with_returns]
        vals_60 = [getattr(s, field) or 0.0 for s in with_60d]
        sub_score_corr_20d[short_name] = _safe_corr(vals_20, fwd_20d_vals)
        sub_score_corr_60d[short_name] = _safe_corr(vals_60, fwd_60d_vals)

    # ── Suggested Re-weighting ──────────────────────────────
    # Average |corr| across 20d and 60d horizons → re-normalize to preserve
    # the current total weight cap (128 pts across the 7 core sub-scores).
    # Sub-scores with negative or near-zero correlation get floored at a
    # small positive (0.02) so they're not zeroed out by a single noisy
    # archive — re-weighting is a *suggestion*, not auto-apply.
    #
    # Load settings via importlib so we don't collide with webapp/backend/config.py
    # (a different module that shadows the project-root config/ package on
    # the backend's sys.path).
    import importlib.util
    _settings_path = os.path.normpath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "config", "settings.py",
    ))
    _spec = importlib.util.spec_from_file_location("_screener_settings", _settings_path)
    _cfg = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_cfg)
    current_weights = {
        "box_tightness":   _cfg.SCORE_BOX_TIGHTNESS,
        "touch_density":   _cfg.SCORE_TOUCH_DENSITY,
        "oscillation":     _cfg.SCORE_OSCILLATION,
        "atr_squeeze":     _cfg.SCORE_ATR_SQUEEZE,
        "lps_tightness":   _cfg.SCORE_LPS_TIGHTNESS,
        "vol_contraction": _cfg.SCORE_VOL_CONTRACTION,
        "base_age":        _cfg.SCORE_BASE_AGE,
    }
    total_cap = sum(current_weights.values())
    # Combine the two horizons. If 60d sample size is too small for stable
    # correlations (the _safe_corr gate is n>=5), fall back to 20d only —
    # otherwise the 60d zeros dilute every sub-score's signal symmetrically
    # and produce a deceptively even suggestion.
    weights_table: List[Dict[str, Any]] = []
    weights_basis = "insufficient_data"
    if len(with_returns) >= 30:
        use_60d = len(with_60d) >= 15
        weights_basis = "20d+60d_avg" if use_60d else "20d_only"
        avg_abs_corr = {}
        for k in current_weights:
            c20 = abs(sub_score_corr_20d.get(k, 0.0) or 0.0)
            if use_60d:
                c60 = abs(sub_score_corr_60d.get(k, 0.0) or 0.0)
                blended = (c20 + c60) / 2
            else:
                blended = c20
            # Floor at 0.02 so a single sub-score with 0 corr doesn't get
            # zeroed out — keeps the suggestion conservative around weak signal.
            avg_abs_corr[k] = max(blended, 0.02)
        norm = sum(avg_abs_corr.values()) or 1.0
        for k, current in current_weights.items():
            suggested = round(total_cap * (avg_abs_corr[k] / norm), 1)
            weights_table.append({
                "name": k,
                "current": current,
                "suggested": suggested,
                "delta": round(suggested - current, 1),
                "avg_abs_corr": round(avg_abs_corr[k], 4),
            })

    # Also correlate structural metrics (20d only — diagnostic, not re-weight input).
    structural_corr = {}
    for field in ["box_width", "base_length", "touches", "atr_ratio", "vol_contraction"]:
        vals = [float(getattr(s, field) or 0) for s in with_returns]
        structural_corr[f"{field}_vs_fwd20d"] = _safe_corr(vals, fwd_20d_vals)

    # ── Setup Type Breakdown ─────────────────────────────────
    type_groups: Dict[str, list] = defaultdict(list)
    for s in with_returns:
        type_groups[s.setup_type].append(s)

    type_breakdown = {}
    for stype, group in sorted(type_groups.items()):
        returns = [s.fwd_return_20d for s in group if s.fwd_return_20d is not None]
        type_breakdown[stype] = {
            "count": len(group),
            "avg_fwd_20d": _safe_mean(returns),
            "win_rate": round(len([r for r in returns if r > 0]) / max(len(returns), 1), 3),
        }

    # ── Market Context Analysis ──────────────────────────────
    spy_groups: Dict[str, list] = defaultdict(list)
    for s in with_returns:
        trend = s.spy_trend or "UNKNOWN"
        spy_groups[trend].append(s)

    market_context = {}
    for trend, group in spy_groups.items():
        returns = [s.fwd_return_20d for s in group if s.fwd_return_20d is not None]
        market_context[trend] = {
            "count": len(group),
            "avg_fwd_20d": _safe_mean(returns),
            "win_rate": round(len([r for r in returns if r > 0]) / max(len(returns), 1), 3),
        }

    return {
        "total_with_returns": len(with_returns),
        "total_with_60d_returns": len(with_60d),
        "tier_performance": tier_perf,
        "sub_score_correlations_20d": sub_score_corr_20d,
        "sub_score_correlations_60d": sub_score_corr_60d,
        "suggested_weights": weights_table,
        "weights_basis": weights_basis,
        "structural_correlations": structural_corr,
        "setup_type_breakdown": type_breakdown,
        "market_context": market_context,
    }


@router.get("/calibration/equity-curve")
def equity_curve(
    tier: Optional[str] = Query(None, description="Filter by tier; default = ALL triggered setups"),
    label: Optional[str] = Query(None, description="Filter by quality_label"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Cumulative R-multiple curve over time — 'if I'd taken every triggered
    setup matching the filter, here's the running P&L in R'.

    Sorted by trigger_date so the curve reflects realistic chronological
    deployment of capital.
    """
    q = db.query(SetupArchive).filter(SetupArchive.triggered == 1, SetupArchive.r_multiple_20d.isnot(None))
    if tier:
        q = q.filter(SetupArchive.tier == tier.upper())
    if label:
        q = q.filter(SetupArchive.quality_label == label)

    setups = q.all()
    if not setups:
        return {"points": [], "summary": {}}

    setups.sort(key=lambda s: s.trigger_date or s.scan_date or "")

    points = []
    cum = 0.0
    for s in setups:
        cum += float(s.r_multiple_20d)
        points.append({
            "date": s.trigger_date or s.scan_date,
            "ticker": s.ticker,
            "tier": s.tier,
            "r": round(float(s.r_multiple_20d), 3),
            "cum_r": round(cum, 3),
        })

    rs = [float(s.r_multiple_20d) for s in setups]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]

    return {
        "points": points,
        "summary": {
            "total_setups": len(setups),
            "total_r": round(cum, 2),
            "win_rate": round(len(wins) / len(rs), 3) if rs else 0,
            "avg_r": round(float(np.mean(rs)), 3) if rs else 0,
            "best_r": round(float(np.max(rs)), 3) if rs else 0,
            "worst_r": round(float(np.min(rs)), 3) if rs else 0,
            "max_drawdown_r": round(_max_drawdown_r(points), 3),
        },
    }


def _max_drawdown_r(points: List[dict]) -> float:
    """Peak-to-trough drawdown of cum_r in R units."""
    if not points:
        return 0.0
    peak = points[0]["cum_r"]
    max_dd = 0.0
    for p in points:
        peak = max(peak, p["cum_r"])
        dd = peak - p["cum_r"]
        if dd > max_dd:
            max_dd = dd
    return float(max_dd)


# ── Manual Actions ───────────────────────────────────────────────

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

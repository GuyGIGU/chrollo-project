"""Archive setup browsing, detail, chart, linked-trade, and label endpoints."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from archive_models import SetupArchive
from core.pipeline.universe import DEFAULT_UNIVERSE_TYPE
from database import get_db
from routers.archive_schemas import EpisodeOut, LabelUpdate, SetupOut
from services.archive_queries import (
    _apply_setup_filters,
    _episode_context,
    _episode_key,
)

router = APIRouter(tags=["archive"])


def _resolve_universe_type(universe_type: Optional[str]) -> Optional[str]:
    """Map the browse ``universe_type`` query param to a filter value.

    Defaults to ``'us_equities'`` (the same scope the stats / calibration surfaces
    use), but ``'all'`` (or an empty value) lifts the filter so the raw browse
    lists can surface sector / commodity setups too — the multi-universe escape
    hatch these list endpoints otherwise lack."""
    if universe_type is None:
        return DEFAULT_UNIVERSE_TYPE
    cleaned = universe_type.strip().lower()
    if cleaned in ("", "all"):
        return None
    return cleaned


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
    universe_type: Optional[str] = Query(
        DEFAULT_UNIVERSE_TYPE, description="Universe scope; 'all' surfaces every universe."
    ),
    sort_by: str = Query("scan_date"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """List archived setups with filtering and sorting."""
    q = _apply_setup_filters(
        db.query(SetupArchive),
        tier=tier, setup_type=setup_type, source=source,
        quality_label=quality_label, min_score=min_score,
        date_from=date_from, date_to=date_to,
        universe_type=_resolve_universe_type(universe_type),
    )

    sort_col = getattr(SetupArchive, sort_by, SetupArchive.scan_date)
    q = q.order_by(sort_col if sort_dir == "asc" else desc(sort_col))
    return q.offset(skip).limit(limit).all()


@router.get("/episodes", response_model=List[EpisodeOut])
def list_episodes(
    skip: int = 0,
    limit: int = 200,
    tier: Optional[str] = Query(None),
    setup_type: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    quality_label: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    universe_type: Optional[str] = Query(
        DEFAULT_UNIVERSE_TYPE, description="Universe scope; 'all' surfaces every universe."
    ),
    sort_by: str = Query("first_seen"),
    sort_dir: str = Query("desc"),
    db: Session = Depends(get_db),
):
    """List setups collapsed to one row per *episode*.

    A persisting base is re-flagged every scan; an episode groups those daily
    re-flags (same ticker + setup_type, consecutive scan dates) into one event
    anchored to the first-seen row — de-duplicating continuation rows so the
    table shows one row per real setup and stats aren't inflated. Grouping runs
    over the full filtered set, then the result is sorted and paginated.
    """
    eps, row_by_id, passed_notes = _episode_context(
        db, tier=tier, setup_type=setup_type, source=source,
        quality_label=quality_label, min_score=min_score,
        date_from=date_from, date_to=date_to,
        universe_type=_resolve_universe_type(universe_type),
    )

    out: List[EpisodeOut] = []
    for ep in eps:
        canonical = SetupOut.model_validate(row_by_id[ep.canonical_id])
        review_key = (ep.ticker, ep.first_seen)
        out.append(EpisodeOut(
            **canonical.model_dump(),
            episode_key=_episode_key(ep.ticker, ep.setup_type, ep.first_seen),
            scan_count=ep.scan_count,
            first_seen=ep.first_seen,
            last_seen=ep.last_seen,
            passed=review_key in passed_notes,
            review_note=passed_notes.get(review_key),
        ))

    # Episodes are derived (not a DB column), so sort in Python. Nulls sort last
    # in either direction so missing returns/scores don't break the comparison.
    non_null = [e for e in out if getattr(e, sort_by, None) is not None]
    nulls = [e for e in out if getattr(e, sort_by, None) is None]
    non_null.sort(key=lambda e: getattr(e, sort_by), reverse=(sort_dir != "asc"))
    out = non_null + nulls

    return out[skip: skip + limit]


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

    import pandas as pd

    from services.market_data import chart_candles, daily_candle_frame

    target_date = pd.Timestamp(setup.scan_date)
    start_date = (target_date - pd.Timedelta(days=500)).strftime('%Y-%m-%d')
    end_date = (target_date + pd.Timedelta(days=45)).strftime('%Y-%m-%d')

    # As-traded candles (regime rule 2026-07-02): rows archived under the
    # as-traded regime overlay with ratio == 1.0 exactly. Pre-cutover
    # div-adjusted rows get the one-bar _adjustment_ratio rescale, which is
    # exact at the scan bar but cannot recover PRE-scan dividend steps — old
    # income-name overlays may sit slightly off far from the scan date
    # (display-only, bounded by the cumulative pre-scan dividends).
    raw = daily_candle_frame(
        setup.ticker, 0, start=start_date, end=end_date, auto_adjust=False
    )
    if raw.empty:
        raise HTTPException(status_code=404, detail="Market data not found for ticker")

    # Re-scale stored R/S/trigger onto the freshly-adjusted candle scale.
    ratio = _adjustment_ratio(raw, target_date, setup.current_price)

    candles, volumes = chart_candles(
        raw,
        up_color='rgba(38, 166, 154, 0.5)',
        down_color='rgba(239, 83, 80, 0.5)',
        require_finite=False,
        volume_as_int=True,
    )
    forward_bars = int((raw.index > target_date).sum())

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


# ── Saw-and-passed marker + missed-winners report ────────────────

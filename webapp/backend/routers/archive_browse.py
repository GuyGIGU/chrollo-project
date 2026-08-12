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
    _ta_grades_by_ids,
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
    min_ta_grade: Optional[float] = Query(
        None, ge=0, le=100,
        description="0-100 grade floor; pre-v2 (NULL-grade) rows are excluded."),
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
        min_ta_grade=min_ta_grade,
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
    min_ta_grade: Optional[float] = Query(
        None, ge=0, le=100,
        description="0-100 floor on the episode's CURRENT grade — its LATEST "
                    "scan's ta_grade (ruled 2026-08-08, operator-delegated: "
                    "the grade ranks what the setup is NOW). The episode keeps "
                    "its true first-seen anchor, scan count, and review marker "
                    "— grouping is grade-independent; episodes whose latest "
                    "scan is ungraded (pre-v2) can never satisfy a floor."),
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
    # min_ta_grade is deliberately NOT a row filter here: grouping runs
    # grade-independent (the cache is shared across grade floors), and the
    # floor applies per EPISODE on its latest member's grade below — so a
    # flip-straddling episode never re-anchors first_seen or sheds its
    # saw-and-passed marker in the filtered view (2026-08-08 review, the
    # R4 semantic fork, operator-delegated).
    eps, row_by_id, passed_notes = _episode_context(
        db, tier=tier, setup_type=setup_type, source=source,
        quality_label=quality_label, min_score=min_score,
        date_from=date_from, date_to=date_to,
        universe_type=_resolve_universe_type(universe_type),
    )
    grade_by_id = {}
    if min_ta_grade is not None:
        grade_by_id = _ta_grades_by_ids(db, [ep.member_ids[-1] for ep in eps])
        eps = [ep for ep in eps
               if grade_by_id.get(ep.member_ids[-1]) is not None
               and grade_by_id[ep.member_ids[-1]] >= min_ta_grade]

    # Sort on raw values, then model_validate ONLY the paginated page (council
    # review 2026-08-05, finding 8): per-row validation now parses the two deep
    # JSON cells, so validating the FULL filtered set before slicing would pay
    # parse-and-discard for every row the page never shows — a cost that grows
    # with the archive. Derived episode fields sort from the episode record;
    # everything else sorts from the canonical ORM row (identical ordering:
    # validation never changes a sortable scalar).
    def _sort_value(ep):
        derived = {
            "episode_key": _episode_key(ep.ticker, ep.setup_type, ep.first_seen),
            "scan_count": ep.scan_count,
            "first_seen": ep.first_seen,
            "last_seen": ep.last_seen,
        }
        if sort_by in derived:
            return derived[sort_by]
        return getattr(row_by_id[ep.canonical_id], sort_by, None)

    # Nulls sort last in either direction so missing returns/scores don't
    # break the comparison.
    non_null = [ep for ep in eps if _sort_value(ep) is not None]
    nulls = [ep for ep in eps if _sort_value(ep) is None]
    non_null.sort(key=_sort_value, reverse=(sort_dir != "asc"))
    page = (non_null + nulls)[skip: skip + limit]

    # The page's CURRENT grades (latest member per episode) — already in
    # hand when the floor ran; fetched page-only otherwise.
    page_latest = [ep.member_ids[-1] for ep in page]
    missing = [i for i in page_latest if i not in grade_by_id]
    if missing:
        grade_by_id.update(_ta_grades_by_ids(db, missing))

    out: List[EpisodeOut] = []
    for ep in page:
        canonical = SetupOut.model_validate(row_by_id[ep.canonical_id])
        review_key = (ep.ticker, ep.first_seen)
        out.append(EpisodeOut(
            **canonical.model_dump(),
            episode_key=_episode_key(ep.ticker, ep.setup_type, ep.first_seen),
            scan_count=ep.scan_count,
            first_seen=ep.first_seen,
            last_seen=ep.last_seen,
            latest_ta_grade=grade_by_id.get(ep.member_ids[-1]),
            passed=review_key in passed_notes,
            review_note=passed_notes.get(review_key),
        ))
    return out


@router.get("/setups/{setup_id}", response_model=SetupOut)
def get_setup(setup_id: int, db: Session = Depends(get_db)):
    """Get a single archived setup by ID."""
    setup = db.query(SetupArchive).filter(SetupArchive.id == setup_id).first()
    if not setup:
        raise HTTPException(status_code=404, detail="Setup not found")
    return setup


def glance_bar_budget(base_length, lps_length) -> int:
    """How many trailing bars the hover glance needs to frame this setup.

    DERIVED, never fixed: the payload's r_anchor/s_anchor are offsets from the
    box start, and the box start is reconstructed downstream as
    len(candles) - 1 - forward_bars - base_len + 1. Hand a window shorter than
    the box and that arithmetic clamps to zero — the rails and the grey root
    swing then paint on the wrong bars, which is a lie rather than a degrade.
    Live archive base lengths run to 433 bars (median 37, p99 196), so any
    constant cap mis-frames the tail. Context beyond the box comes on top.
    """
    base = int(base_length or 0)
    lps = int(lps_length or 0)
    return max(130, base + lps + 25)


@router.get("/setups/{setup_id}/chart")
def get_setup_chart(setup_id: int, glance: bool = False, db: Session = Depends(get_db)):
    """Fetch historical data for a specific setup and format it for ScreenerModal.

    `glance=1` trims the RESPONSE to the bars a hover-size chart can actually
    show. The provider window is deliberately identical either way so both calls
    share one market-data cache key — a hover followed by a click must not cost
    two vendor pulls for the same name. Everything else about the envelope is
    unchanged; the un-parameterized call is byte-identical to before.
    """
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

    if glance:
        # Trim the OLDEST bars only. forward_bars counts bars after the scan, so
        # it is measured from the right edge and survives the cut untouched;
        # base_len is likewise anchored to the right, so dropping leading
        # context cannot move the box.
        keep = glance_bar_budget(setup.base_length, setup.lps_length) + forward_bars
        if keep < len(candles):
            candles = candles[-keep:]
            volumes = volumes[-keep:]

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

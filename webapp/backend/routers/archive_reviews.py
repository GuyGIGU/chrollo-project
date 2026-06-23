"""Archive review markers and missed-winner report endpoints."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from routers.archive_schemas import ReviewMarkIn, ReviewToggleIn
from services.archive_queries import _episode_context, _latest_episode_first_seen
from services.db_write import commit_or_http

router = APIRouter(tags=["archive"])


@router.post("/reviews/toggle")
def toggle_review(payload: ReviewToggleIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Toggle a 'saw & passed' marker for a setup; returns the new state.

    Callers pass an explicit ``scan_date`` (an archive-table row) or omit it
    (a live screener card), in which case it resolves to the ticker's current
    episode first-seen — the same key the archive and missed-winners report use.
    Lets the missed-winners report tell 'reviewed but skipped' apart from
    'never engaged'.
    """
    from datetime import datetime

    from models import SetupReview

    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker required")
    scan_date = (payload.scan_date or "").strip()
    if not scan_date:
        scan_date = _latest_episode_first_seen(db, ticker)
        if not scan_date:
            raise HTTPException(status_code=404, detail=f"No archived setup for {ticker} to mark")

    existing = (
        db.query(SetupReview)
        .filter(SetupReview.ticker == ticker, SetupReview.scan_date == scan_date)
        .first()
    )
    if existing:
        db.delete(existing)
        commit_or_http(db)
        return {"ticker": ticker, "scan_date": scan_date, "passed": False}

    db.add(SetupReview(
        ticker=ticker, scan_date=scan_date, verdict="passed", created_at=datetime.utcnow(),
    ))
    commit_or_http(db, conflict_detail="Review marker already exists")
    return {"ticker": ticker, "scan_date": scan_date, "passed": True}


@router.post("/reviews/mark")
def mark_review(payload: ReviewMarkIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Mark an episode as reviewed/passed and store the skip reason in note."""
    from datetime import datetime

    from models import SetupReview

    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker required")
    scan_date = (payload.scan_date or "").strip()
    if not scan_date:
        scan_date = _latest_episode_first_seen(db, ticker)
        if not scan_date:
            raise HTTPException(status_code=404, detail=f"No archived setup for {ticker} to mark")

    note = (payload.note or "").strip() or None
    existing = (
        db.query(SetupReview)
        .filter(SetupReview.ticker == ticker, SetupReview.scan_date == scan_date)
        .first()
    )
    if existing:
        existing.verdict = "passed"
        existing.note = note
    else:
        db.add(SetupReview(
            ticker=ticker,
            scan_date=scan_date,
            verdict="passed",
            note=note,
            created_at=datetime.utcnow(),
        ))
    commit_or_http(db, conflict_detail="Review marker already exists")
    return {"ticker": ticker, "scan_date": scan_date, "passed": True, "review_note": note}


@router.get("/reviews/passed")
def list_passed_reviews(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Distinct tickers carrying a 'saw & passed' marker, so the live screener
    can show which of today's cards you've already reviewed and skipped."""
    from models import SetupReview

    rows = (
        db.query(SetupReview.ticker)
        .filter(SetupReview.verdict == "passed")
        .distinct()
        .all()
    )
    return {"tickers": sorted({r.ticker for r in rows})}


@router.get("/missed-winners")
def missed_winners_report(
    min_r: float = Query(2.0, ge=0),
    source: str = Query("screener"),
    trade_window_days: int = Query(7, ge=0, le=30),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Engine-validation payoff: winners (>= min_r in 60d) the engine flagged,
    bucketed by traded / saw-and-passed / never-engaged.

    Built on episodes so a persisting base isn't double-counted. The winner
    tallies fill in as 60-day forward returns mature; until then matured==0.
    """
    import pandas as pd

    from core.archive import missed_winners as mw
    from models import TradeLog

    eps, row_by_id, passed_keys = _episode_context(db, source=source)

    # Index trade opens by UPPER-cased ticker so a manually-logged lower/mixed
    # case ticker still matches the (upper-case) archive ticker — otherwise a
    # setup you traded is misread as 'never engaged'.
    trades_by_ticker: Dict[str, List[str]] = defaultdict(list)
    for t_ticker, t_open in db.query(TradeLog.ticker, TradeLog.opening_date).all():
        if t_ticker and t_open:
            trades_by_ticker[t_ticker.upper()].append(t_open)

    def _engagement(ep) -> mw.Engagement:
        # TRADED dominates: a real position on this ticker within ±window of any
        # of the episode's scan days.
        opens = trades_by_ticker.get(ep.ticker.upper(), [])
        if opens:
            lo = pd.Timestamp(ep.first_seen) - pd.Timedelta(days=trade_window_days)
            hi = pd.Timestamp(ep.last_seen) + pd.Timedelta(days=trade_window_days)
            for od in opens:
                try:
                    if lo <= pd.Timestamp(od) <= hi:
                        return mw.Engagement.TRADED
                except (ValueError, TypeError):
                    continue
        if (ep.ticker, ep.first_seen) in passed_keys:
            return mw.Engagement.SAW_AND_PASSED
        return mw.Engagement.NEVER_ENGAGED

    outcomes = [
        mw.EpisodeOutcome(
            ticker=ep.ticker,
            first_seen=ep.first_seen,
            tier=row_by_id[ep.canonical_id].tier,
            score=row_by_id[ep.canonical_id].score,
            r_multiple_60d=row_by_id[ep.canonical_id].r_multiple_60d,
            engagement=_engagement(ep),
        )
        for ep in eps
    ]
    return mw.summarize(outcomes, min_r=min_r)


# ── Stats & Calibration ─────────────────────────────────────────

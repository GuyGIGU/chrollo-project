"""Archive review markers and missed-winner report endpoints."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from routers.archive_schemas import ReadVerdictIn, ReviewMarkIn, ReviewToggleIn
from services.archive_queries import _episode_context, _latest_episode_first_seen

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
        db.commit()
        return {"ticker": ticker, "scan_date": scan_date, "passed": False}

    db.add(SetupReview(
        ticker=ticker, scan_date=scan_date, verdict="passed", created_at=datetime.utcnow(),
    ))
    db.commit()
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
    db.commit()
    return {"ticker": ticker, "scan_date": scan_date, "passed": True, "review_note": note}


_READ_VERDICTS = {"agree", "disagree"}
# The grade channel's closed vocabulary (task 14) — write-time refusal is the
# live DB's operative constraint (the ALTER path strips model CHECKs).
_GRADE_VERDICTS = {"agree", "too_high", "too_low"}


def _read_verdict_key(payload_universe: str | None) -> str:
    """Resolve the identity's universe leg: the payload's scan_identity value
    verbatim, or the equities-default scope (EC-1 one source) when absent."""
    from core.pipeline.universe import default_universe_type

    return (payload_universe or "").strip() or default_universe_type()


@router.post("/reviews/read-verdict")
def set_read_verdict(payload: ReadVerdictIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Record (or clear) the operator's verdict on the ENGINE'S READ — the
    concordance axis, distinct from 'considered' and 'saw & passed'. Bound
    verbatim to the archive identity triple (ticker, scan_date, universe_type);
    a missing identity is a 400, never an episode fallback (the read differs
    scan to scan). ``engine_config_version`` stamps the evidence version the
    operator saw and is refreshed on every re-record.

    RULED (council review 2026-08-05, finding 6 note; OPERATOR-CONFIRMED
    2026-08-05): a verdict on a scan that never reached the archive
    (cache-mode / stale-cohort abort / AP-9 readable-but-never-archived) is
    ACCEPTED — those payloads show real reads worth grading. The concordance
    reader must therefore LEFT-join verdicts to setup_archive and SURFACE
    unmatched ones, never drop them silently ("so we won't drop anything that
    might provide value")."""
    from sqlalchemy.exc import IntegrityError

    from models import ReadVerdict

    ticker = payload.ticker.strip().upper()
    scan_date = payload.scan_date.strip()
    if not ticker or not scan_date:
        raise HTTPException(status_code=400, detail="ticker and scan_date required")
    universe_type = _read_verdict_key(payload.universe_type)
    verdict = payload.verdict
    if verdict is not None:
        # An empty string is a malformed verdict (422) — NEVER coerced into
        # the null clear sentinel; clearing requires an explicit null.
        verdict = verdict.strip().lower()
        if verdict not in _READ_VERDICTS:
            raise HTTPException(status_code=422,
                                detail=f"verdict must be one of {sorted(_READ_VERDICTS)} or null")
    grade_verdict = payload.grade_verdict
    if grade_verdict is not None:
        grade_verdict = grade_verdict.strip().lower()
        if grade_verdict not in _GRADE_VERDICTS:
            raise HTTPException(
                status_code=422,
                detail=f"grade_verdict must be one of {sorted(_GRADE_VERDICTS)} or null")
        if verdict is None:
            # The schema makes grade-without-read unrepresentable (verdict is
            # NOT NULL) — refuse the combination loudly instead of accepting
            # the payload and silently discarding a validated judgment with
            # the deleted row (2026-08-08 review, finding 6).
            raise HTTPException(
                status_code=422,
                detail="a grade verdict requires a read verdict — clearing "
                       "the read verdict clears the grade verdict with it")
    note = (payload.note or "").strip() or None
    ecv = (payload.engine_config_version or "").strip() or None

    def _find():
        return (
            db.query(ReadVerdict)
            .filter(ReadVerdict.ticker == ticker,
                    ReadVerdict.scan_date == scan_date,
                    ReadVerdict.universe_type == universe_type)
            .first()
        )

    identity = {"ticker": ticker, "scan_date": scan_date, "universe_type": universe_type}
    existing = _find()
    if verdict is None:
        if existing:
            db.delete(existing)
            db.commit()
        # Same keys on every branch (finding 6: the clear branch's shape
        # disagreed with its two siblings).
        return {**identity, "verdict": None, "grade_verdict": None, "note": None}
    if existing:
        existing.verdict = verdict
        existing.grade_verdict = grade_verdict
        existing.note = note
        existing.engine_config_version = ecv
        db.commit()
        return {**identity, "verdict": verdict,
                "grade_verdict": grade_verdict, "note": note}
    try:
        db.add(ReadVerdict(ticker=ticker, scan_date=scan_date,
                           universe_type=universe_type, verdict=verdict,
                           grade_verdict=grade_verdict,
                           note=note, engine_config_version=ecv,
                           created_at=datetime.utcnow()))
        db.commit()
    except IntegrityError:
        # Concurrent double-POST of the same key (routers run in a threadpool):
        # converge to the last verdict instead of surfacing a 500 that would
        # trip the frontend's rollback for a write that effectively landed.
        db.rollback()
        existing = _find()
        if existing is None:
            raise
        existing.verdict = verdict
        existing.grade_verdict = grade_verdict
        existing.note = note
        existing.engine_config_version = ecv
        db.commit()
    return {**identity, "verdict": verdict,
            "grade_verdict": grade_verdict, "note": note}


@router.get("/reviews/read-verdict")
def get_read_verdict(
    ticker: str = Query(..., min_length=1, max_length=12),
    scan_date: str = Query(..., min_length=8, max_length=10),
    universe_type: str = Query(None, max_length=32),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """The current read verdict for one identity triple, nulls when none.
    ``universe_type`` omitted resolves to the equities-default scope, matching
    the POST's resolution. Serves the FULL stored judgment — grade_verdict
    included; a persisted value the read path refused to serve was a
    write-only, self-erasing channel (2026-08-08 review, finding 6)."""
    from models import ReadVerdict

    row = (
        db.query(ReadVerdict)
        .filter(ReadVerdict.ticker == ticker.strip().upper(),
                ReadVerdict.scan_date == scan_date.strip(),
                ReadVerdict.universe_type == _read_verdict_key(universe_type))
        .first()
    )
    return {"verdict": row.verdict if row else None,
            "grade_verdict": row.grade_verdict if row else None,
            "note": row.note if row else None}


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

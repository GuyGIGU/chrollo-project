"""User-curated screener watchlist: dated save events with server-resolved
pins + snapshots (Finviz plan Tasks 6-7).

The three original routes keep their observable contracts (GET active-only,
POST dated save, DELETE deactivates-keeping-history) so the frontend toggle
survives the ledger transition; weekly review and replay are new siblings.
Thin router — the decisions live in services/watchlist_ledger.py."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from database import get_db
from marks_validity import TICKER_RE
from routers.calibration import require_same_app
from services import watchlist_ledger

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
logger = logging.getLogger("chrollo.watchlist")


class WatchlistItem(BaseModel):
    """The toggle contract: ``ticker`` + ``created_at`` (now the save's audit
    stamp) survive from the pre-ledger shape; the pin fields are additive."""

    ticker: str
    created_at: datetime | None = None
    save_date: str | None = None
    pinned: bool = False
    pin_scan_date: str | None = None


class SaveIn(BaseModel):
    """What the operator clicked: the DISPLAYED scan identity — never a chart
    payload (EC-26; the server snapshots its own artifact). Optional so the
    bare legacy POST still works."""

    universe: str = "us_stocks"
    scan_date: Optional[str] = Field(
        None, min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")


class ReviewSaveOut(BaseModel):
    id: int
    ticker: str
    save_date: str
    saved_at: datetime | None
    unstarred_at: datetime | None
    active: bool
    origin: str
    pinned: bool
    pin_scan_date: str | None
    pin_universe_type: str | None
    pin_setup_type: str | None
    pin_engine_config_version: str | None
    has_snapshot: bool
    # Display fields quoted from the STORED snapshot (EC-28): the row and its
    # replay read the same bytes, so they cannot disagree.
    tier: str | None
    score: float | None
    setup: str | None
    ta_grade: str | None
    price: float | None


class ReviewWeek(BaseModel):
    week_start: str
    saves: List[ReviewSaveOut]


class ReviewResponse(BaseModel):
    weeks: List[ReviewWeek]


class ReplayResponse(BaseModel):
    watch: ReviewSaveOut
    snapshot_status: str
    archive_status: str
    snapshot: Dict | None
    archive: Dict | None


def _item(row: models.Watchlist) -> WatchlistItem:
    return WatchlistItem(
        ticker=row.ticker,
        created_at=row.saved_at,
        save_date=row.save_date,
        pinned=row.pin_scan_date is not None,
        pin_scan_date=row.pin_scan_date,
    )


def _valid_symbol(ticker: str) -> str:
    sym = ticker.strip().upper()
    if not sym or not TICKER_RE.match(sym):
        logger.info("watchlist bad_ticker %r", ticker)
        raise HTTPException(status_code=400, detail={
            "class": "bad_ticker",
            "message": "Ticker must match the symbol pattern",
        })
    return sym


@router.get("/", response_model=List[WatchlistItem])
def list_watchlist(db: Session = Depends(get_db)):
    return [_item(row) for row in watchlist_ledger.active_watches(db)]


@router.post("/{ticker}", response_model=WatchlistItem,
             dependencies=[Depends(require_same_app)])
def add_to_watchlist(ticker: str, payload: SaveIn | None = None,
                     db: Session = Depends(get_db)):
    sym = _valid_symbol(ticker)
    body = payload or SaveIn()
    try:
        row, outcome = watchlist_ledger.save_watch(
            db, sym, body.universe, body.scan_date)
    except ValueError:
        # resolve_universe's closed registry refused the key.
        logger.info("watchlist bad_universe %r", body.universe)
        raise HTTPException(status_code=422, detail={
            "class": "bad_universe",
            "message": f"Unknown universe key: {body.universe!r}",
        })
    logger.info("watchlist save %s -> %s", sym, outcome)
    return _item(row)


@router.delete("/{ticker}", dependencies=[Depends(require_same_app)])
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    sym = _valid_symbol(ticker)
    row = watchlist_ledger.unstar_watch(db, sym)
    if row is None:
        raise HTTPException(status_code=404, detail={
            "class": "not_on_watchlist",
            "message": "Ticker not on watchlist",
        })
    return {"status": "removed", "ticker": sym}


@router.get("/review", response_model=ReviewResponse)
def watchlist_review(limit_weeks: int = Query(12, ge=1, le=104),
                     db: Session = Depends(get_db)):
    return ReviewResponse(weeks=watchlist_ledger.weekly_review(db, limit_weeks))


@router.get("/{watch_id}/replay", response_model=ReplayResponse)
def watchlist_replay(watch_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Watchlist, watch_id)
    if row is None:
        raise HTTPException(status_code=404, detail={
            "class": "not_found",
            "message": f"No watchlist save with id {watch_id}",
        })
    return ReplayResponse(**watchlist_ledger.replay(db, row))

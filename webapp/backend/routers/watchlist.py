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
from marks_validity import TICKER_RE, parse_iso_date
from routers.calibration import require_same_app
from services import watchlist_ledger

router = APIRouter(prefix="/watchlist", tags=["watchlist"])
logger = logging.getLogger("chrollo.watchlist")


class WatchlistItem(BaseModel):
    """The toggle contract: ``ticker`` + ``created_at`` (now the save's audit
    stamp) survive from the pre-ledger shape; the pin fields are additive.

    ``id`` is the ACTIVE save event's row id. The active row is by construction
    the ticker's most recent save (``save_watch`` returns the active row before
    creating anything, and a partial unique index allows only one), so a surface
    that wants that save's stored chart can hop straight to
    ``/watchlist/{id}/replay`` instead of paging the weekly review to find it.
    Nullable because an optimistic row has not been assigned one yet."""

    id: int | None = None
    ticker: str
    created_at: datetime | None = None
    save_date: str | None = None
    pinned: bool = False
    pin_scan_date: str | None = None
    # The pin's registry KEY (EC-37): what the candle endpoint's `universe`
    # parameter wants, so a pinned name always draws from the panel its saved
    # setup came from. None on unpinned rows.
    pin_universe_key: str | None = None


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
    # The registry KEY a re-star POSTs back as its displayed universe.
    pin_universe_key: str | None
    pin_setup_type: str | None
    pin_engine_config_version: str | None
    has_snapshot: bool
    # Display fields quoted from the STORED snapshot (EC-28): the row and its
    # replay read the same bytes, so they cannot disagree. ta_grade is the
    # producer's NUMERIC 0-100 grade (dashboard writes round(float, 1)).
    tier: str | None
    score: float | None
    setup: str | None
    ta_grade: float | None
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
        id=row.id,
        ticker=row.ticker,
        created_at=row.saved_at,
        save_date=row.save_date,
        pinned=row.pin_scan_date is not None,
        pin_scan_date=row.pin_scan_date,
        pin_universe_key=watchlist_ledger.universe_key_for_type(
            row.pin_universe_type),
    )


def valid_symbol(ticker: str) -> str:
    """Normalize + validate a path ticker against the ONE strict grammar
    (marks_validity.TICKER_RE) or 400. Shared with the candle router — a
    ticker the watchlist accepted must never be one the candle wire rejects
    (one folded judgment, never a twin)."""
    sym = ticker.strip().upper()
    if not sym or not TICKER_RE.match(sym):
        logger.info("bad_ticker %r", ticker)
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
    sym = valid_symbol(ticker)
    body = payload or SaveIn()
    # The Field pattern is shape-only; a calendar-impossible date would slip
    # through to the artifact equality check and silently degrade the pin —
    # refuse it at the boundary instead (Hunt: strings match nothing quietly).
    if body.scan_date is not None and parse_iso_date(body.scan_date) is None:
        raise HTTPException(status_code=400, detail={
            "class": "bad_date",
            "message": "scan_date must be a real YYYY-MM-DD date",
        })
    # Validate the universe key AT THE BOUNDARY, before the save runs — this
    # 422 may only ever name the registry's refusal, so the resolve is the
    # only call inside the try. Wrapping the whole save would relabel any
    # future ValueError in snapshot/JSON/DB work as "unknown universe"
    # (council review 2026-08-17, finding 14).
    from core.pipeline.universe import resolve_universe
    try:
        resolve_universe(body.universe)
    except ValueError:
        logger.info("watchlist bad_universe %r", body.universe)
        raise HTTPException(status_code=422, detail={
            "class": "bad_universe",
            "message": f"Unknown universe key: {body.universe!r}",
        })
    row, outcome = watchlist_ledger.save_watch(
        db, sym, body.universe, body.scan_date)
    logger.info("watchlist save %s -> %s", sym, outcome)
    return _item(row)


@router.delete("/{ticker}", dependencies=[Depends(require_same_app)])
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    sym = valid_symbol(ticker)
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

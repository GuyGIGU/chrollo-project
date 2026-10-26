"""User-curated screener watchlist: dated save events with server-resolved
pins + snapshots (Finviz plan Tasks 6-7).

The three original routes keep their observable contracts (GET active-only,
POST dated save, DELETE deactivates-keeping-history) so the frontend toggle
survives the ledger transition; weekly review and replay are new siblings.
Thin router — the decisions live in domains/watchlist/ledger.py."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Annotated, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import models
from database import get_db
from domains.calibration.validation import TICKER_RE, parse_iso_date
from app.dependencies import require_same_app
from domains.watchlist import best_gains
from domains.watchlist import ledger as watchlist_ledger

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
    # Historical display facts from the stored snapshot, never a fresh quote.
    saved_setup: str | None = None
    saved_price: float | None = None
    saved_market_cap: float | None = None
    saved_sector: str | None = None
    saved_industry: str | None = None
    # The saved scan's trigger and next earnings, for a name tonight's scan dropped.
    saved_trigger: float | None = None
    saved_next_earnings: str | None = None
    saved_earnings_confirmed: bool | None = None
    # The weekly list: the week it is on, the scan before the add, and his marks.
    week_start: str | None = None
    basis_scan_date: str | None = None
    side: str = "L"
    ready: int = 0
    ready_at: datetime | None = None


class SaveIn(BaseModel):
    """What the operator clicked: the DISPLAYED scan identity — never a chart
    payload (EC-26; the server snapshots its own artifact). Optional so the
    bare legacy POST still works."""

    universe: str = "us_stocks"
    scan_date: Optional[str] = Field(
        None, min_length=10, max_length=10, pattern=r"^\d{4}-\d{2}-\d{2}$")
    # None = keep the side the name had (the screener star, Undo); a new save is long.
    side: Optional[Literal["L", "S"]] = None


class MarkIn(BaseModel):
    """This week's hand marks: L/S, and ready 0 (watching) / 1 ✓ / 2 ✓✓."""

    side: Optional[Literal["L", "S"]] = None
    ready: Optional[Literal[0, 1, 2]] = None


class WeeksOut(BaseModel):
    current: str | None
    weeks: List[str]


# A week is named by its Monday; absent = this week.
WeekParam = Annotated[Optional[str], Query(pattern=r"^\d{4}-\d{2}-\d{2}$")]


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


class BestGainsOut(BaseModel):
    """One active save's "% Best Diff" columns (domains/watchlist/best_gains.py):
    fractions of the saved scan day's high, null where there is no pin or no bar since."""

    status: str
    last_bar_date: str | None
    since_add: float | None
    d60: float | None
    d30: float | None
    d14: float | None
    d7: float | None
    d2: float | None
    # What the live columns divide by: the scan day's high, the close before
    # the quote's trading day, and the 52-week distance at the last close.
    basis: float | None
    prev_close: float | None
    dist_52w_high: float | None


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
        week_start=row.week_start,
        basis_scan_date=row.basis_scan_date,
        side=row.side,
        ready=row.ready,
        ready_at=row.ready_at,
        **watchlist_ledger.saved_display_fields(row.snapshot_json),
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
def list_watchlist(db: Session = Depends(get_db), week: WeekParam = None):
    """This week's list by default; ``week`` (its Monday) reads a past week as it ended."""
    return [_item(row) for row in watchlist_ledger.active_watches(db, week)]


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
        db, sym, body.universe, body.scan_date, body.side)
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


@router.patch("/{ticker}", response_model=WatchlistItem,
              dependencies=[Depends(require_same_app)])
def mark_watchlist(ticker: str, payload: MarkIn, db: Session = Depends(get_db)):
    sym = valid_symbol(ticker)
    row = watchlist_ledger.mark_watch(db, sym, side=payload.side, ready=payload.ready)
    if row is None:
        raise HTTPException(status_code=404, detail={
            "class": "not_on_watchlist",
            "message": "Ticker not on this week's watchlist",
        })
    return _item(row)


@router.get("/weeks", response_model=WeeksOut)
def watchlist_weeks(db: Session = Depends(get_db)):
    return watchlist_ledger.list_weeks(db)


def _session_day(now: datetime | None = None) -> str:
    """The trading day a live quote belongs to: today in New York from the
    09:30 open, the day before until then (the quote is still the last close),
    and the Friday before on a weekend (holidays are not modelled). Display only."""
    from zoneinfo import ZoneInfo

    now = now or datetime.now(ZoneInfo("America/New_York"))
    day = now.date()
    if (now.hour, now.minute) < (9, 30):
        day -= timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.isoformat()


@router.get("/best-gains", response_model=Dict[str, BestGainsOut])
def watchlist_best_gains(db: Session = Depends(get_db), week: WeekParam = None):
    return best_gains.for_watches(watchlist_ledger.active_watches(db, week), _session_day())


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

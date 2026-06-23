"""User-curated screener watchlist: save tickers from the grid for later review."""
from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db
from services.db_write import commit_or_http

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistItem(BaseModel):
    ticker: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


@router.get("/", response_model=List[WatchlistItem])
def list_watchlist(db: Session = Depends(get_db)):
    return (
        db.query(models.Watchlist)
        .order_by(models.Watchlist.created_at.desc())
        .all()
    )


@router.post("/{ticker}", response_model=WatchlistItem)
def add_to_watchlist(ticker: str, db: Session = Depends(get_db)):
    sym = ticker.strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="Ticker required")
    existing = db.query(models.Watchlist).filter(models.Watchlist.ticker == sym).first()
    if existing:
        return existing
    item = models.Watchlist(ticker=sym, created_at=datetime.utcnow())
    db.add(item)
    commit_or_http(db, conflict_detail=f"{sym} is already on the watchlist")
    db.refresh(item)
    return item


@router.delete("/{ticker}")
def remove_from_watchlist(ticker: str, db: Session = Depends(get_db)):
    sym = ticker.strip().upper()
    item = db.query(models.Watchlist).filter(models.Watchlist.ticker == sym).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ticker not on watchlist")
    db.delete(item)
    commit_or_http(db)
    return {"status": "removed", "ticker": sym}

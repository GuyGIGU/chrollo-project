"""Trade CRUD and journal metric endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from routers import journal as journal_router
from services.db_write import commit_or_http
from services.journal_stats import calculate_journal_stats

router = APIRouter(prefix="", tags=["trades"])


@router.get("/trades/", response_model=List[schemas.TradeLog])
def read_trades(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return db.query(models.TradeLog).offset(skip).limit(limit).all()


@router.post("/trades/", response_model=schemas.TradeLog)
def create_trade(trade: schemas.TradeLogCreate, db: Session = Depends(get_db)):
    db_trade = models.TradeLog(**trade.model_dump())
    db.add(db_trade)
    commit_or_http(db)
    db.refresh(db_trade)
    return db_trade


@router.put("/trades/{trade_id}", response_model=schemas.TradeLog)
def update_trade(trade_id: int, trade_update: schemas.TradeLogUpdate, db: Session = Depends(get_db)):
    db_trade = _get_trade(db, trade_id)
    for key, value in trade_update.model_dump(exclude_unset=True).items():
        setattr(db_trade, key, value)

    commit_or_http(db)
    db.refresh(db_trade)
    return db_trade


@router.delete("/trades/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)):
    db_trade = _get_trade(db, trade_id)
    db.delete(db_trade)
    commit_or_http(db)
    journal_router.wipe_trade_uploads(trade_id)
    return {"status": "Trade deleted successfully"}


@router.get("/journal-stats/")
def get_journal_stats(db: Session = Depends(get_db)):
    return calculate_journal_stats(db.query(models.TradeLog).all())


def _get_trade(db: Session, trade_id: int) -> models.TradeLog:
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade

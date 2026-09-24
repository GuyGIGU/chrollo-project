"""CRUD + attach/detach endpoints for trade tags."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db
from domains.trading.schemas import TagOut  # single source of truth (was duplicated here)

router = APIRouter(prefix="", tags=["tags"])


VALID_CATEGORIES = {"setup", "mistake", "custom"}


class TagCreate(BaseModel):
    name: str
    category: str = "custom"
    color: Optional[str] = None


class TagUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None


def _serialize(tag: models.Tag) -> dict:
    return {"id": tag.id, "name": tag.name, "category": tag.category, "color": tag.color}


@router.get("/tags/", response_model=List[TagOut])
def list_tags(db: Session = Depends(get_db)):
    return db.query(models.Tag).order_by(models.Tag.category, models.Tag.name).all()


@router.post("/tags/", response_model=TagOut)
def create_tag(payload: TagCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Tag name required")
    category = payload.category or "custom"
    if category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {sorted(VALID_CATEGORIES)}")
    existing = db.query(models.Tag).filter(models.Tag.name == name).first()
    if existing:
        return existing
    tag = models.Tag(name=name, category=category, color=payload.color)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: TagUpdate, db: Session = Depends(get_db)):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    if payload.category is not None and payload.category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"category must be one of {sorted(VALID_CATEGORIES)}")
    for field in ("name", "category", "color"):
        val = getattr(payload, field)
        if val is not None:
            setattr(tag, field, val)
    db.commit()
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    db.commit()
    return {"status": "deleted"}


@router.get("/trades/{trade_id}/tags", response_model=List[TagOut])
def list_trade_tags(trade_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade.tags


class AttachPayload(BaseModel):
    tag_ids: List[int]


@router.put("/trades/{trade_id}/tags", response_model=List[TagOut])
def set_trade_tags(trade_id: int, payload: AttachPayload, db: Session = Depends(get_db)):
    """Replace the full set of tags on a trade."""
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    if payload.tag_ids:
        tags = db.query(models.Tag).filter(models.Tag.id.in_(payload.tag_ids)).all()
    else:
        tags = []
    trade.tags = tags
    db.commit()
    db.refresh(trade)
    return trade.tags


@router.post("/trades/{trade_id}/tags/{tag_id}", response_model=List[TagOut])
def attach_tag(trade_id: int, tag_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not trade or not tag:
        raise HTTPException(status_code=404, detail="Trade or tag not found")
    if tag not in trade.tags:
        trade.tags.append(tag)
        db.commit()
        db.refresh(trade)
    return trade.tags


@router.delete("/trades/{trade_id}/tags/{tag_id}", response_model=List[TagOut])
def detach_tag(trade_id: int, tag_id: int, db: Session = Depends(get_db)):
    trade = db.query(models.TradeLog).filter(models.TradeLog.id == trade_id).first()
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not trade or not tag:
        raise HTTPException(status_code=404, detail="Trade or tag not found")
    if tag in trade.tags:
        trade.tags.remove(tag)
        db.commit()
        db.refresh(trade)
    return trade.tags

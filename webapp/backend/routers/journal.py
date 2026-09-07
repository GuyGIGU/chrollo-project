"""Trade journal: plan, notes, attachments, and executions endpoints."""
from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from datetime import datetime
from typing import Optional


def uuid_hex() -> str:
    return uuid.uuid4().hex

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import models
from database import get_db, get_trade_or_404

router = APIRouter(prefix="", tags=["journal"])

UPLOAD_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
_UPLOAD_ROOT_REAL = os.path.realpath(UPLOAD_ROOT)
ALLOWED_MIMES = {"image/png", "image/jpeg", "image/webp"}
MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
_CHUNK = 64 * 1024


def _is_under_upload_root(path: str) -> bool:
    """Guard against serving files outside UPLOAD_ROOT even if stored_path is corrupted."""
    try:
        real = os.path.realpath(path)
    except OSError:
        return False
    return real == _UPLOAD_ROOT_REAL or real.startswith(_UPLOAD_ROOT_REAL + os.sep)


class PlanPayload(BaseModel):
    thesis: Optional[str] = None
    entry_plan: Optional[str] = None
    exit_plan: Optional[str] = None
    risk_plan: Optional[str] = None


class NotePayload(BaseModel):
    body: Optional[str] = None
    mood: Optional[str] = None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def wipe_trade_uploads(trade_id: int) -> None:
    """Delete the on-disk upload directory for a trade. Called from trade delete."""
    trade_dir = os.path.join(UPLOAD_ROOT, str(trade_id))
    if os.path.isdir(trade_dir):
        shutil.rmtree(trade_dir, ignore_errors=True)


# ── Plan ─────────────────────────────────────────────────────────
def _plan_dict(trade_id: int, plan: Optional[models.TradePlan]) -> dict:
    if not plan:
        return {
            "trade_log_id": trade_id,
            "thesis": None,
            "entry_plan": None,
            "exit_plan": None,
            "risk_plan": None,
            "created_at": None,
        }
    return {
        "trade_log_id": plan.trade_log_id,
        "thesis": plan.thesis,
        "entry_plan": plan.entry_plan,
        "exit_plan": plan.exit_plan,
        "risk_plan": plan.risk_plan,
        "created_at": _iso(plan.created_at),
    }


@router.get("/trades/{trade_id}/plan")
def get_plan(trade_id: int, db: Session = Depends(get_db)):
    get_trade_or_404(db, trade_id)
    plan = db.query(models.TradePlan).filter(models.TradePlan.trade_log_id == trade_id).first()
    return _plan_dict(trade_id, plan)


@router.put("/trades/{trade_id}/plan")
def set_plan(trade_id: int, payload: PlanPayload, db: Session = Depends(get_db)):
    get_trade_or_404(db, trade_id)
    plan = db.query(models.TradePlan).filter(models.TradePlan.trade_log_id == trade_id).first()
    if not plan:
        plan = models.TradePlan(trade_log_id=trade_id, created_at=datetime.utcnow())
        db.add(plan)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, key, value)
    db.commit()
    db.refresh(plan)
    return _plan_dict(trade_id, plan)


# ── Notes ────────────────────────────────────────────────────────
def _note_dict(trade_id: int, note: Optional[models.TradeNote]) -> dict:
    if not note:
        return {
            "trade_log_id": trade_id,
            "body": None,
            "mood": None,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "trade_log_id": note.trade_log_id,
        "body": note.body,
        "mood": note.mood,
        "created_at": _iso(note.created_at),
        "updated_at": _iso(note.updated_at),
    }


@router.get("/trades/{trade_id}/notes")
def get_note(trade_id: int, db: Session = Depends(get_db)):
    get_trade_or_404(db, trade_id)
    note = db.query(models.TradeNote).filter(models.TradeNote.trade_log_id == trade_id).first()
    return _note_dict(trade_id, note)


@router.put("/trades/{trade_id}/notes")
def set_note(trade_id: int, payload: NotePayload, db: Session = Depends(get_db)):
    get_trade_or_404(db, trade_id)
    note = db.query(models.TradeNote).filter(models.TradeNote.trade_log_id == trade_id).first()
    now = datetime.utcnow()
    if not note:
        note = models.TradeNote(trade_log_id=trade_id, created_at=now, updated_at=now)
        db.add(note)
    else:
        note.updated_at = now
    note.body = payload.body
    note.mood = payload.mood
    db.commit()
    db.refresh(note)
    return _note_dict(trade_id, note)


# ── Attachments ──────────────────────────────────────────────────
def _attachment_dict(a: models.TradeAttachment, request: Optional[Request] = None) -> dict:
    if request is not None:
        base = str(request.base_url).rstrip("/")
    else:
        base = "http://localhost:8000"
    return {
        "id": a.id,
        "trade_log_id": a.trade_log_id,
        "kind": a.kind,
        "filename": a.filename,
        "mime": a.mime,
        "size_bytes": a.size_bytes,
        "uploaded_at": _iso(a.uploaded_at),
        "url": f"{base}/attachments/{a.id}/file",
    }


@router.get("/trades/{trade_id}/attachments")
def list_attachments(trade_id: int, request: Request, db: Session = Depends(get_db)):
    get_trade_or_404(db, trade_id)
    rows = (
        db.query(models.TradeAttachment)
        .filter(models.TradeAttachment.trade_log_id == trade_id)
        .order_by(models.TradeAttachment.uploaded_at.desc(), models.TradeAttachment.id.desc())
        .all()
    )
    return [_attachment_dict(a, request) for a in rows]


@router.post("/trades/{trade_id}/attachments")
def upload_attachment(
    trade_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    get_trade_or_404(db, trade_id)
    mime = (file.content_type or "").lower()
    if mime not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail=f"Only {sorted(ALLOWED_MIMES)} allowed")

    # Stream into a hasher + temp file so we fail fast on oversized uploads
    # instead of pulling the whole body into memory first. Sync def (house
    # rule) so the hashing and the disk writes run in the threadpool, not on
    # the event loop — the same shape as the IBKR CSV import, milder because
    # the work is chunked, still the loop's to block (council 2026-09-07, F12).
    ext = MIME_EXT.get(mime, "bin")
    trade_dir = os.path.join(UPLOAD_ROOT, str(trade_id))
    if not _is_under_upload_root(trade_dir):
        raise HTTPException(status_code=400, detail="Invalid trade path")
    os.makedirs(trade_dir, exist_ok=True)

    tmp_path = os.path.join(trade_dir, f".tmp.{uuid_hex()}.{ext}")
    hasher = hashlib.sha256()
    total = 0
    try:
        with open(tmp_path, "wb") as fh:
            while True:
                chunk = file.file.read(_CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise HTTPException(status_code=413, detail="File too large (10 MB max)")
                hasher.update(chunk)
                fh.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        sha = hasher.hexdigest()
        stored_name = f"{sha}.{ext}"
        stored_path = os.path.join(trade_dir, stored_name)
        if os.path.exists(stored_path):
            os.remove(tmp_path)
        else:
            os.replace(tmp_path, stored_path)
    except HTTPException:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    att = models.TradeAttachment(
        trade_log_id=trade_id,
        kind="chart",
        filename=file.filename or stored_name,
        stored_path=stored_path,
        mime=mime,
        size_bytes=total,
        uploaded_at=datetime.utcnow(),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return _attachment_dict(att, request)


@router.get("/attachments/{attachment_id}/file")
def serve_attachment(attachment_id: int, db: Session = Depends(get_db)):
    a = db.query(models.TradeAttachment).filter(models.TradeAttachment.id == attachment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if not _is_under_upload_root(a.stored_path):
        raise HTTPException(status_code=400, detail="Invalid attachment path")
    if not os.path.exists(a.stored_path):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(
        a.stored_path,
        media_type=a.mime or "application/octet-stream",
        filename=a.filename,
    )


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, db: Session = Depends(get_db)):
    a = db.query(models.TradeAttachment).filter(models.TradeAttachment.id == attachment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Attachment not found")
    # Only remove file if no other row references the same stored_path (hash dedupe safety).
    same_path_count = (
        db.query(models.TradeAttachment)
        .filter(
            models.TradeAttachment.stored_path == a.stored_path,
            models.TradeAttachment.id != a.id,
        )
        .count()
    )
    try:
        if same_path_count == 0 and os.path.exists(a.stored_path):
            os.remove(a.stored_path)
    except OSError:
        pass
    db.delete(a)
    db.commit()
    return {"status": "deleted"}


# ── Executions tab ───────────────────────────────────────────────
@router.get("/trades/{trade_id}/executions")
def list_trade_executions(trade_id: int, db: Session = Depends(get_db)):
    get_trade_or_404(db, trade_id)
    rows = (
        db.query(models.Execution)
        .filter(models.Execution.trade_log_id == trade_id)
        .order_by(models.Execution.time.asc(), models.Execution.id.asc())
        .all()
    )
    return [
        {
            "id": e.id,
            "exec_id": e.exec_id,
            "symbol": e.symbol,
            "side": e.side,
            "quantity": e.quantity,
            "price": e.price,
            "commission": e.commission or 0.0,
            "realized_pnl": e.realized_pnl,
            "time": _iso(e.time),
        }
        for e in rows
    ]

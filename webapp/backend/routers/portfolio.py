"""REST endpoints for the Portfolio tab."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from ibkr import get_ibkr_service
from services import csv_import
from services.portfolio_snapshot import flatten_summary, stored_executions

router = APIRouter(prefix="", tags=["portfolio"])

# Reject statement uploads larger than this. Typical multi-year statements are
# under 1 MB; anything bigger is almost certainly the wrong file.
_MAX_CSV_BYTES = 5 * 1024 * 1024


@router.get("/portfolio/account-summary")
def account_summary() -> Dict[str, Any]:
    summary = get_ibkr_service().get_account_summary()
    return flatten_summary(summary)


@router.get("/portfolio/positions")
def positions() -> List[Dict[str, Any]]:
    return get_ibkr_service().get_positions()


@router.get("/portfolio/open-orders")
def open_orders() -> List[Dict[str, Any]]:
    return get_ibkr_service().get_open_orders()


@router.get("/portfolio/executions")
def executions(db: Session = Depends(get_db), limit: int = 100) -> List[Dict[str, Any]]:
    """Return stored executions persisted by auto-import."""
    return stored_executions(db, limit)


@router.post("/ibkr/import-csv")
async def import_ibkr_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Bulk import an IBKR Activity Statement CSV."""
    raw = await file.read()
    if len(raw) > _MAX_CSV_BYTES:
        size_mb = _MAX_CSV_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"CSV too large (>{size_mb} MB)")
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        content = _decode_statement(raw)
        return csv_import.import_activity_statement(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _decode_statement(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")

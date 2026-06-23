"""Small helpers for safe database writes from API routes."""
from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

log = logging.getLogger("chrollo.db")


def commit_or_http(
    db,
    *,
    conflict_detail: str = "That record already exists",
    error_detail: str = "Database write failed",
) -> None:
    """Commit a request-scoped session or convert DB failures to clean HTTP errors."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_detail) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        log.exception("database commit failed")
        raise HTTPException(status_code=500, detail=error_detail) from exc

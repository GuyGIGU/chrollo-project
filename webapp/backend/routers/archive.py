"""Archive API router aggregator."""
from __future__ import annotations

from fastapi import APIRouter

from routers import archive_actions, archive_browse, archive_calibration, archive_reviews

router = APIRouter(prefix="/archive", tags=["archive"])
router.include_router(archive_browse.router)
router.include_router(archive_reviews.router)
router.include_router(archive_calibration.router)
router.include_router(archive_actions.router)

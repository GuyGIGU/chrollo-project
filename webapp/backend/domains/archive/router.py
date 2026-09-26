"""Archive API router aggregator."""
from __future__ import annotations

from fastapi import APIRouter

from domains.archive import actions as archive_actions
from domains.archive import browse as archive_browse
from domains.archive import calibration as archive_calibration
from domains.archive import reviews as archive_reviews

router = APIRouter(prefix="/archive", tags=["archive"])
router.include_router(archive_browse.router)
router.include_router(archive_reviews.router)
router.include_router(archive_calibration.router)
router.include_router(archive_actions.router)

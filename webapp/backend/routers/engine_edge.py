"""Read-only engine-edge endpoint for the Home command-center pulse.

A thin GET over ``services.engine_edge`` (which wraps the pure edge report). The
response model pins the bias-safety contract so the provenance flags survive
serialization untouched — the UI renders an honest pulse off ``n_unbiased`` /
``unbiased`` / ``contaminated_input`` and treats ``headline_mfe_median is None``
as the "not enough data" state.
"""
from __future__ import annotations

from typing import Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.engine_edge import engine_edge

router = APIRouter(prefix="/engine-edge", tags=["engine-edge"])


class TierEdge(BaseModel):
    n: int
    mfe_median: Optional[float]
    mfe_n: int
    win_rate: Optional[float]
    n_labelled: int


class EngineEdgeResponse(BaseModel):
    unbiased: bool
    contaminated_input: bool
    n_unbiased: int
    headline_mfe_col: str
    headline_mfe_median: Optional[float]
    headline_mfe_n: int
    abnormal_median: Optional[float]
    by_tier: Dict[str, TierEdge]


# Plain ``def`` on purpose: the archive read + pandas pass are CPU/IO-bound, so
# Starlette dispatches this to the threadpool and never blocks the event loop.
@router.get("/", response_model=EngineEdgeResponse)
def get_engine_edge() -> dict:
    return engine_edge()

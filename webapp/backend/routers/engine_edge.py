"""Read-only engine-edge endpoint for the Home command-center pulse.

A thin GET over ``services.engine_edge`` (which wraps the pure edge report). The
response model pins the bias-safety contract so the provenance flags survive
serialization untouched — the UI renders an honest pulse off ``n_unbiased`` /
``unbiased`` / ``contaminated_input`` and treats ``headline_mfe_median is None``
as the "not enough data" state.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.engine_edge import engine_edge

router = APIRouter(prefix="/engine-edge", tags=["engine-edge"])


class TailBand(BaseModel):
    """One measured exceedance band. The THRESHOLD travels with the rate so the
    frontend labels what the backend measured instead of re-declaring it (EC-28)."""
    threshold: Optional[float]
    rate: Optional[float]


class TailRates(BaseModel):
    n: int
    col: Optional[str]
    bands: List[TailBand]


class TierEdge(BaseModel):
    n: int
    mfe_median: Optional[float]
    mfe_n: int
    win_rate: Optional[float]
    n_labelled: int
    resolution_rate: Optional[float]
    tail: TailRates


class EngineEdgeResponse(BaseModel):
    unbiased: bool
    contaminated_input: bool
    n_unbiased: int
    headline_mfe_col: str
    headline_mfe_median: Optional[float]
    headline_mfe_n: int
    abnormal_median: Optional[float]
    tail: TailRates
    by_tier: Dict[str, TierEdge]


# Plain ``def`` on purpose: the archive read + pandas pass are CPU/IO-bound, so
# Starlette dispatches this to the threadpool and never blocks the event loop.
@router.get("/", response_model=EngineEdgeResponse)
def get_engine_edge() -> dict:
    return engine_edge()

"""Read-only engine-edge endpoint for the Home command-center pulse.

A thin GET over ``domains.archive.edge`` (which wraps the pure edge report). The
response model pins the bias-safety contract so the provenance flags survive
serialization untouched — the UI renders an honest pulse off ``n_unbiased`` /
``unbiased`` / ``contaminated_input`` and treats ``headline_mfe_median is None``
as the "not enough data" state.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from domains.archive.edge import engine_edge

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


class ReaderBaseline(TierEdge):
    """The other reader's fires, one line under the tiers, never pooled with them."""
    reader: str
    first_scan: Optional[str]
    last_scan: Optional[str]


class EngineEdgeResponse(BaseModel):
    # Which reader the headline and the tiers measure ('new' / 'old'): the one that
    # wrote the latest scan, from its first scan day. The other is the baseline
    # (his word Mon 12/10/2026, option A: an old S and a new S are not one letter).
    reader: Optional[str] = None
    reader_since: Optional[str] = None
    baseline: Optional[ReaderBaseline] = None
    unbiased: bool
    contaminated_input: bool
    n_unbiased: int
    headline_mfe_col: str
    headline_mfe_median: Optional[float]
    headline_mfe_n: int
    abnormal_median: Optional[float]
    tail: TailRates
    by_tier: Dict[str, TierEdge]
    # His calibration setups beside the fires, never pooled (ruling 2026-10-03).
    calibration: Optional[TierEdge] = None


# Plain ``def`` on purpose: the archive read + pandas pass are CPU/IO-bound, so
# Starlette dispatches this to the threadpool and never blocks the event loop.
@router.get("/", response_model=EngineEdgeResponse)
def get_engine_edge() -> dict:
    return engine_edge()

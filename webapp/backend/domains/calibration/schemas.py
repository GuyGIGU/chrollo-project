"""Calibration mark request and response shapes."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class EventIn(BaseModel):
    event_type: str
    start_date: str
    end_date: str
    tip_date: Optional[str] = None
    tip_price: Optional[float] = None
    # The mini-consolidation's price band (a small box). Every field here must
    # be a real CalibrationMarkEvent column — _apply_payload constructs the row
    # with **model_dump().
    band_high: Optional[float] = None
    band_low: Optional[float] = None
    source: str = "operator"


class MarkIn(BaseModel):
    """Full mark payload. Cross-field sanity lives in the ONE shared judgment
    (marks_validity) — this model only shapes/types the boundary."""
    ticker: str
    as_of_date: str
    label: str = ""
    verdict: str
    resistance: Optional[float] = None
    support: Optional[float] = None
    box_start_date: Optional[str] = None
    box_end_date: Optional[str] = None
    r_anchor_date: Optional[str] = None
    s_anchor_date: Optional[str] = None
    first_rail: Optional[str] = None
    # The Trigger (the operator's buy) — shape here, semantics in shared validity
    # (box-only, requires an LPS, forward-of-as-of); the frame-dependent upper
    # bound (a real session <= frame_end) is enforced at the write boundary.
    trigger_date: Optional[str] = None
    trigger_price: Optional[float] = None
    rails_source: str = "operator"
    knowable_from_date: Optional[str] = None
    note: Optional[str] = None
    data_regime: str
    engine_config_version: str
    anchor_close: float
    frame_digest: Optional[str] = None
    events: List[EventIn] = []


class EventOut(EventIn):
    id: int
    model_config = {"from_attributes": True}


class MarkOut(BaseModel):
    id: int
    ticker: str
    as_of_date: str
    label: str
    verdict: str
    resistance: Optional[float] = None
    support: Optional[float] = None
    box_start_date: Optional[str] = None
    box_end_date: Optional[str] = None
    r_anchor_date: Optional[str] = None
    s_anchor_date: Optional[str] = None
    first_rail: Optional[str] = None
    # Presented as explicit null (never omitted) so the client can always read
    # "no buy marked" without guessing.
    trigger_date: Optional[str] = None
    trigger_price: Optional[float] = None
    rails_source: str
    knowable_from_date: Optional[str] = None
    note: Optional[str] = None
    data_regime: str
    engine_config_version: str
    anchor_close: float
    frame_digest: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    revision: int
    events: List[EventOut] = []

    model_config = {"from_attributes": True}



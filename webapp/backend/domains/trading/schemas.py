from pydantic import BaseModel
from typing import List, Optional


class TagOut(BaseModel):
    id: int
    name: str
    category: str
    color: Optional[str] = None

    model_config = {"from_attributes": True}

class TradeLogBase(BaseModel):
    opening_date: str
    direction: str
    ticker: str
    entry_price: float
    stop_loss: float
    quantity: int
    risk_percentage: Optional[float] = None
    position_size: float
    target_r: float = 3.0

    t1_qty: Optional[int] = None
    t1_price: Optional[float] = None
    t2_qty: Optional[int] = None
    t2_price: Optional[float] = None
    t3_qty: Optional[int] = None
    t3_price: Optional[float] = None
    t4_qty: Optional[int] = None
    t4_price: Optional[float] = None
    t5_qty: Optional[int] = None
    t5_price: Optional[float] = None

    closing_date: Optional[str] = None
    remaining_qty: Optional[int] = None
    exit_price: Optional[float] = None
    commissions: Optional[float] = 0.0
    pnl: Optional[float] = None
    actions_json: Optional[str] = None

    # Intent capture: 1-10 pre-trade conviction + one-line exit reason.
    conviction: Optional[int] = None
    exit_reason: Optional[str] = None

class TradeLogCreate(TradeLogBase):
    pass

class TradeLogUpdate(BaseModel):
    opening_date: Optional[str] = None
    direction: Optional[str] = None
    ticker: Optional[str] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    quantity: Optional[int] = None
    risk_percentage: Optional[float] = None
    position_size: Optional[float] = None
    target_r: Optional[float] = None
    t1_qty: Optional[int] = None
    t1_price: Optional[float] = None
    t2_qty: Optional[int] = None
    t2_price: Optional[float] = None
    t3_qty: Optional[int] = None
    t3_price: Optional[float] = None
    t4_qty: Optional[int] = None
    t4_price: Optional[float] = None
    t5_qty: Optional[int] = None
    t5_price: Optional[float] = None
    closing_date: Optional[str] = None
    remaining_qty: Optional[int] = None
    exit_price: Optional[float] = None
    commissions: Optional[float] = None
    pnl: Optional[float] = None
    actions_json: Optional[str] = None
    conviction: Optional[int] = None
    exit_reason: Optional[str] = None

class TradeLog(TradeLogBase):
    id: int
    tags: List[TagOut] = []

    model_config = {"from_attributes": True}

"""Position sizing helper endpoint."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="", tags=["position-calculator"])


@router.post("/calculate-position/")
def calculate_position(risk_amount: float, entry_price: float, stop_price: float, direction: str = "L"):
    if entry_price <= 0 or stop_price <= 0 or risk_amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid inputs. Must be positive.")

    stop_distance = abs(entry_price - stop_price)
    if stop_distance == 0:
        raise HTTPException(status_code=400, detail="Entry and Stop price cannot be the same.")

    shares = int(risk_amount / stop_distance)
    return {
        "shares": shares,
        "stop_distance": round(stop_distance, 4),
        "position_size": round(shares * entry_price, 2),
    }

"""Server-side open-trade risk math for stop and target alerts.

Parity notes:
- Stop distance and R-to-stop mirror
  webapp/frontend/src/utils/tradeTableUtils.js lines 254-265.
- Target ladder hit/next/distance logic mirrors lines 298-335.
- Stop-tone bands mirror riskToneFor on lines 339-345.
- Alert thresholds mirror stopAlertFor/targetAlertFor/targetHitAlertFor on
  lines 347-425.

MVP simplification: this module uses TradeLog.entry_price and stop_loss
directly instead of porting summarizeFillLedger's fill-ledger VWAP. That keeps
server-side alerts useful for the always-on sweep while leaving full fill-ledger
parity as a later refinement.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetRisk:
    index: int
    label: str
    price: float
    qty: float | None
    hit: bool
    is_next: bool
    r_to_target: float | None
    pct_to_target: float | None


@dataclass(frozen=True)
class TradeRisk:
    trade_id: int | str
    ticker: str
    direction: str
    is_long: bool
    entry_price: float
    stop_loss: float
    current_price: float
    position: float
    risk_distance: float
    r_to_stop: float
    dist_to_stop_pct: float
    stop_tone: str | None
    target_ladder: list[TargetRisk]
    next_target: TargetRisk | None
    status: str


def evaluate_open_trade(trade, price) -> TradeRisk | None:
    """Evaluate an open TradeLog against the current price."""
    if getattr(trade, "closing_date", None) or getattr(trade, "pnl", None) is not None:
        return None

    ticker = str(getattr(trade, "ticker", "") or "").strip().upper()
    entry_price = _finite_positive(getattr(trade, "entry_price", None))
    stop_loss = _finite_positive(getattr(trade, "stop_loss", None))
    current_price = _finite_positive(price)
    if not ticker or entry_price is None or stop_loss is None or current_price is None:
        return None

    position = _open_position(trade)
    if position is None:
        return None

    risk_distance = abs(entry_price - stop_loss)
    if risk_distance <= 0:
        return None

    direction = infer_direction(trade)
    is_long = direction == "LONG"
    dist_to_stop = current_price - stop_loss if is_long else stop_loss - current_price
    dist_to_stop_pct = dist_to_stop / current_price * 100
    r_to_stop = dist_to_stop / risk_distance
    target_ladder = build_target_ladder(
        current_price=current_price,
        is_long=is_long,
        risk_distance=risk_distance,
        trade=trade,
    )
    next_target = next((target for target in target_ladder if target.is_next), None)

    return TradeRisk(
        trade_id=getattr(trade, "id", None) or ticker,
        ticker=ticker,
        direction=direction,
        is_long=is_long,
        entry_price=entry_price,
        stop_loss=stop_loss,
        current_price=current_price,
        position=position,
        risk_distance=risk_distance,
        r_to_stop=r_to_stop,
        dist_to_stop_pct=dist_to_stop_pct,
        stop_tone=risk_tone_for(r_to_stop),
        target_ladder=target_ladder,
        next_target=next_target,
        status=_status_for(trade, position),
    )


def build_target_ladder(
    *,
    current_price: float,
    is_long: bool,
    risk_distance: float,
    trade,
) -> list[TargetRisk]:
    targets: list[TargetRisk] = []
    for index in range(1, 6):
        target_price = _finite_positive(getattr(trade, f"t{index}_price", None))
        if target_price is None:
            continue

        signed_distance = target_price - current_price if is_long else current_price - target_price
        hit = current_price >= target_price if is_long else current_price <= target_price
        targets.append(
            TargetRisk(
                index=index,
                label=f"T{index}",
                price=target_price,
                qty=_finite_positive(getattr(trade, f"t{index}_qty", None)),
                hit=hit,
                is_next=False,
                r_to_target=signed_distance / risk_distance if risk_distance else None,
                pct_to_target=signed_distance / current_price * 100 if current_price else None,
            )
        )

    next_index = next((target.index for target in targets if not target.hit), None)
    return [
        TargetRisk(
            index=target.index,
            label=target.label,
            price=target.price,
            qty=target.qty,
            hit=target.hit,
            is_next=target.index == next_index,
            r_to_target=target.r_to_target,
            pct_to_target=target.pct_to_target,
        )
        for target in targets
    ]


def infer_direction(trade) -> str:
    direction = str(getattr(trade, "direction", "") or "").upper()
    if direction in {"L", "LONG"}:
        return "LONG"
    if direction in {"S", "SHORT"}:
        return "SHORT"

    entry = _finite_positive(getattr(trade, "entry_price", None))
    stop = _finite_positive(getattr(trade, "stop_loss", None))
    if entry is not None and stop is not None and stop != 0:
        return "LONG" if stop < entry else "SHORT"
    return "LONG"


def risk_tone_for(r_to_stop: float | None) -> str | None:
    if r_to_stop is None:
        return None
    if r_to_stop <= 0:
        return "breached"
    if r_to_stop <= 0.25:
        return "danger"
    if r_to_stop <= 0.5:
        return "warning"
    return None


def _open_position(trade) -> float | None:
    quantity = _finite_positive(getattr(trade, "quantity", None))
    if quantity is None:
        return None

    remaining_qty = getattr(trade, "remaining_qty", None)
    if remaining_qty is not None:
        try:
            remaining = abs(float(remaining_qty))
        except (TypeError, ValueError):
            remaining = 0
        if remaining > 0:
            return remaining
        return None
    return quantity


def _status_for(trade, position: float) -> str:
    quantity = _finite_positive(getattr(trade, "quantity", None))
    if quantity is not None and 0 < position < quantity:
        return "partial"
    return "open"


def _finite_positive(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number != number:
        return None
    return number

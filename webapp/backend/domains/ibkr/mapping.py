"""Helpers to convert ib_async objects to plain dicts suitable for JSON / DB."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _to_naive_utc(dt: datetime) -> datetime:
    """Normalize to naive UTC — the executions table's canonical timezone.

    ib_async hands out tz-aware UTC execution times; SQLite storage strips the
    tzinfo, so making the conversion explicit here keeps every stored time
    unambiguously UTC (CSV-imported statement times are normalized the same way).
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _as_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except Exception:
        return None


def contract_symbol(contract: Any) -> str:
    """Best-effort human symbol for a contract (STK uses symbol, OPT uses localSymbol)."""
    if contract is None:
        return ""
    sec_type = getattr(contract, "secType", "") or ""
    if sec_type == "OPT":
        local = getattr(contract, "localSymbol", "") or ""
        if local:
            return local
    return getattr(contract, "symbol", "") or ""


def position_to_dict(position: Any) -> Dict[str, Any]:
    contract = getattr(position, "contract", None)
    return {
        "account": getattr(position, "account", None),
        "symbol": contract_symbol(contract),
        "sec_type": getattr(contract, "secType", None) if contract else None,
        "exchange": getattr(contract, "exchange", None) if contract else None,
        "currency": getattr(contract, "currency", None) if contract else None,
        "quantity": _as_float(getattr(position, "position", 0)),
        "avg_cost": _as_float(getattr(position, "avgCost", 0)),
    }


def portfolio_item_to_dict(item: Any) -> Dict[str, Any]:
    contract = getattr(item, "contract", None)
    return {
        "account": getattr(item, "account", None),
        "symbol": contract_symbol(contract),
        "sec_type": getattr(contract, "secType", None) if contract else None,
        "exchange": getattr(contract, "exchange", None) if contract else None,
        "currency": getattr(contract, "currency", None) if contract else None,
        "quantity": _as_float(getattr(item, "position", 0)),
        "market_price": _as_float(getattr(item, "marketPrice", 0)),
        "market_value": _as_float(getattr(item, "marketValue", 0)),
        "avg_cost": _as_float(getattr(item, "averageCost", 0)),
        "unrealized_pnl": _as_float(getattr(item, "unrealizedPNL", 0)),
        "realized_pnl": _as_float(getattr(item, "realizedPNL", 0)),
    }


def execution_to_dict(exec_obj: Any, contract: Any, commission_report: Any = None) -> Dict[str, Any]:
    """Convert an ib_async Execution (+ optional CommissionReport) into a plain dict."""
    raw = {
        "exec": {k: getattr(exec_obj, k, None) for k in (
            "execId", "permId", "orderId", "clientId", "acctNumber",
            "side", "shares", "price", "time", "cumQty", "avgPrice",
        )},
        "contract": {k: getattr(contract, k, None) for k in (
            "symbol", "secType", "exchange", "currency", "localSymbol", "multiplier",
        )} if contract else None,
    }

    side = (getattr(exec_obj, "side", "") or "").upper()
    side_norm = "BUY" if side.startswith("B") else "SELL"

    time_val = getattr(exec_obj, "time", None)
    if isinstance(time_val, datetime):
        time_dt = time_val
    else:
        try:
            time_dt = datetime.fromisoformat(str(time_val)) if time_val else datetime.utcnow()
        except Exception:
            time_dt = datetime.utcnow()
    time_dt = _to_naive_utc(time_dt)

    commission = None
    realized = None
    if commission_report is not None:
        commission = _as_float(getattr(commission_report, "commission", None))
        realized = _as_float(getattr(commission_report, "realizedPNL", None))

    return {
        "exec_id": getattr(exec_obj, "execId", None),
        "perm_id": str(getattr(exec_obj, "permId", "") or "") or None,
        "order_id": str(getattr(exec_obj, "orderId", "") or "") or None,
        "account": getattr(exec_obj, "acctNumber", None),
        "symbol": contract_symbol(contract),
        "sec_type": getattr(contract, "secType", None) if contract else None,
        "side": side_norm,
        "quantity": _as_float(getattr(exec_obj, "shares", 0)) or 0.0,
        "price": _as_float(getattr(exec_obj, "price", 0)) or 0.0,
        "multiplier": _as_float(getattr(contract, "multiplier", None)) if contract else None,
        "commission": commission or 0.0,
        "realized_pnl": realized,
        "time": time_dt,
        "raw_json": json.dumps(raw, default=str),
    }


def order_to_dict(trade: Any) -> Dict[str, Any]:
    """Convert an ib_async Trade (order + contract + status) to a dict."""
    order = getattr(trade, "order", None)
    contract = getattr(trade, "contract", None)
    status = getattr(trade, "orderStatus", None)
    return {
        "order_id": getattr(order, "orderId", None) if order else None,
        "perm_id": str(getattr(order, "permId", "") or "") or None if order else None,
        "account": getattr(order, "account", None) if order else None,
        "symbol": contract_symbol(contract),
        "sec_type": getattr(contract, "secType", None) if contract else None,
        "action": getattr(order, "action", None) if order else None,
        "order_type": getattr(order, "orderType", None) if order else None,
        "total_quantity": _as_float(getattr(order, "totalQuantity", 0)) if order else None,
        "limit_price": _as_float(getattr(order, "lmtPrice", None)) if order else None,
        "stop_price": _as_float(getattr(order, "auxPrice", None)) if order else None,
        "status": getattr(status, "status", None) if status else None,
        "filled": _as_float(getattr(status, "filled", 0)) if status else None,
        "remaining": _as_float(getattr(status, "remaining", 0)) if status else None,
        "avg_fill_price": _as_float(getattr(status, "avgFillPrice", None)) if status else None,
    }

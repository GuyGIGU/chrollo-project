"""REST + SSE endpoints for the Portfolio tab."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from fastapi import Depends

import models
from database import get_db
from ibkr import get_ibkr_service
from ibkr.broadcaster import broadcaster

router = APIRouter(prefix="", tags=["portfolio"])


SUMMARY_KEYS = (
    "NetLiquidation",
    "TotalCashValue",
    "AvailableFunds",
    "BuyingPower",
    "GrossPositionValue",
    "UnrealizedPnL",
    "RealizedPnL",
    "DayTradesRemaining",
)


def _flatten_summary(summary: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Collapse the {account: {tag: {value, currency}}} map into a single dict.

    Sums numeric values across accounts; non-numeric values fall back to the first seen.
    """
    out: Dict[str, Any] = {}
    currency: Dict[str, str] = {}
    for account, bucket in summary.items():
        for tag, entry in bucket.items():
            if tag not in SUMMARY_KEYS:
                continue
            val = entry.get("value")
            cur = entry.get("currency") or ""
            try:
                fval = float(val)
                out[tag] = out.get(tag, 0.0) + fval
                currency.setdefault(tag, cur)
            except (TypeError, ValueError):
                out.setdefault(tag, val)
    return {"values": out, "currency": currency, "raw": summary}


@router.get("/portfolio/account-summary")
def account_summary() -> Dict[str, Any]:
    svc = get_ibkr_service()
    summary = svc.get_account_summary()
    return _flatten_summary(summary)


@router.get("/portfolio/positions")
def positions() -> List[Dict[str, Any]]:
    return get_ibkr_service().get_positions()


@router.get("/portfolio/open-orders")
def open_orders() -> List[Dict[str, Any]]:
    return get_ibkr_service().get_open_orders()


@router.get("/portfolio/executions")
def executions(db: Session = Depends(get_db), limit: int = 100) -> List[Dict[str, Any]]:
    """Return stored executions (persisted by auto-import) + any not-yet-flushed ones."""
    rows = (
        db.query(models.Execution)
        .order_by(models.Execution.time.desc(), models.Execution.id.desc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "id": r.id,
            "exec_id": r.exec_id,
            "account": r.account,
            "symbol": r.symbol,
            "sec_type": r.sec_type,
            "side": r.side,
            "quantity": r.quantity,
            "price": r.price,
            "commission": r.commission,
            "realized_pnl": r.realized_pnl,
            "time": r.time.isoformat() if r.time else None,
            "trade_log_id": r.trade_log_id,
        })
    return out


def _snapshot_payload() -> Dict[str, Any]:
    svc = get_ibkr_service()
    snap = svc.snapshot()
    return {
        "connected": snap["connected"],
        "mode": snap["mode"],
        "stale": snap.get("stale", False),
        "daily_restart": snap.get("daily_restart", False),
        "session_competition": snap.get("session_competition", False),
        "last_update": snap["last_update"],
        "account_summary": _flatten_summary(snap["account_summary"]),
        "positions": snap["portfolio"] or snap["positions"],
        "open_orders": snap["open_orders"],
        "recent_executions": snap["recent_executions"][-50:],
    }


@router.get("/stream/portfolio")
async def stream_portfolio(request: Request) -> StreamingResponse:
    """SSE stream of the combined portfolio snapshot.

    Pushes the full snapshot on any IBKR update, plus a heartbeat every 15s so the
    browser's EventSource stays open through idle periods.

    Resilience: if the broadcaster's loop dies (IBKR reconnect), the generator
    catches the exception and re-subscribes automatically.
    """

    async def gen():
        # Send an initial snapshot so the UI has something to render immediately.
        yield f"data: {json.dumps(_snapshot_payload(), default=str)}\n\n"

        while True:
            if await request.is_disconnected():
                return

            try:
                sub = broadcaster.subscribe("portfolio")
                status_sub = broadcaster.subscribe("ibkr_status")
                tasks = {
                    asyncio.create_task(sub.__anext__()): ("portfolio", sub),
                    asyncio.create_task(status_sub.__anext__()): ("status", status_sub),
                }

                try:
                    while True:
                        if await request.is_disconnected():
                            return
                        done, _ = await asyncio.wait(
                            tasks.keys(), timeout=15, return_when=asyncio.FIRST_COMPLETED
                        )
                        if not done:
                            # Heartbeat — also re-send current snapshot so frontend
                            # stays up-to-date with stale/connected flags
                            yield f": keep-alive\n\n"
                            yield f"data: {json.dumps(_snapshot_payload(), default=str)}\n\n"
                            continue
                        for t in done:
                            channel, it = tasks.pop(t)
                            try:
                                _payload = t.result()
                            except (StopAsyncIteration, Exception):
                                # Subscriber died (loop rebind) — break to re-subscribe
                                for remaining in tasks:
                                    remaining.cancel()
                                tasks.clear()
                                break
                            yield f"data: {json.dumps(_snapshot_payload(), default=str)}\n\n"
                            tasks[asyncio.create_task(it.__anext__())] = (channel, it)
                        if not tasks:
                            break  # re-subscribe in outer loop
                finally:
                    for t in tasks:
                        t.cancel()

            except Exception:
                # Broadcaster died or loop changed — wait briefly and retry
                await asyncio.sleep(1)
                yield f"data: {json.dumps(_snapshot_payload(), default=str)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/stream/executions")
async def stream_executions(request: Request) -> StreamingResponse:
    """Push-only stream of raw IBKR fills as they arrive."""

    async def gen():
        sub = broadcaster.subscribe("executions")
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(sub.__anext__(), timeout=15)
                    yield f"data: {json.dumps(payload, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                except StopAsyncIteration:
                    break
        finally:
            pass

    return StreamingResponse(gen(), media_type="text/event-stream")

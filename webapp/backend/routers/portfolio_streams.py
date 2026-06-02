"""SSE endpoints for live Portfolio updates."""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from ibkr.broadcaster import broadcaster
from services.portfolio_snapshot import portfolio_snapshot_payload

router = APIRouter(prefix="", tags=["portfolio"])

_PORTFOLIO_CHANNELS = ("portfolio", "ibkr_status", "orders", "executions")


def _sse_data(payload: Any) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def _snapshot_event() -> str:
    payload = await asyncio.to_thread(portfolio_snapshot_payload)
    return _sse_data(payload)


async def _stream_snapshot_events(request: Request) -> AsyncIterator[str]:
    yield await _snapshot_event()

    while True:
        if await request.is_disconnected():
            return
        try:
            async for event in _subscribed_snapshots(request):
                yield event
        except Exception:
            await asyncio.sleep(1)
            yield await _snapshot_event()


async def _subscribed_snapshots(request: Request) -> AsyncIterator[str]:
    subscribers = [broadcaster.subscribe(channel) for channel in _PORTFOLIO_CHANNELS]
    tasks = {asyncio.create_task(sub.__anext__()): sub for sub in subscribers}
    try:
        while True:
            if await request.is_disconnected():
                return

            done, _ = await asyncio.wait(
                tasks.keys(), timeout=15, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                yield ": keep-alive\n\n"
                yield await _snapshot_event()
                continue

            for task in done:
                subscriber = tasks.pop(task)
                try:
                    task.result()
                except (StopAsyncIteration, Exception):
                    return
                yield await _snapshot_event()
                tasks[asyncio.create_task(subscriber.__anext__())] = subscriber
    finally:
        for task in tasks:
            task.cancel()


@router.get("/stream/portfolio")
async def stream_portfolio(request: Request) -> StreamingResponse:
    return StreamingResponse(_stream_snapshot_events(request), media_type="text/event-stream")


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
                    yield _sse_data(payload)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                except StopAsyncIteration:
                    break
        finally:
            pass

    return StreamingResponse(gen(), media_type="text/event-stream")

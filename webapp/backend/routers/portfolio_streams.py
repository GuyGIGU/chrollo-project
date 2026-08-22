"""SSE endpoints for live Portfolio updates."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from core.pipeline.json_safety import to_json_safe
from ibkr.broadcaster import broadcaster
from services.portfolio_snapshot import portfolio_snapshot_payload

router = APIRouter(prefix="", tags=["portfolio"])
logger = logging.getLogger("chrollo.portfolio_streams")

_PORTFOLIO_CHANNELS = ("portfolio", "ibkr_status", "orders", "executions")

_IDLE_TIMEOUT_S = 15

# Sentinel _channel_events yields on an idle window (vs a real payload).
_KEEP_ALIVE = object()

# EC-20 shape: the streams degrade-and-retry, but never blind — each distinct
# failure logs loudly ONCE, so the 1 Hz retry loop cannot flood the log while
# a persistent defect still leaves a trace.
_LOGGED_FAILURES: set[tuple[str, str]] = set()


def _log_stream_failure_once(where: str, exc: BaseException) -> None:
    key = (where, f"{type(exc).__name__}: {exc}")
    if key in _LOGGED_FAILURES:
        return
    if len(_LOGGED_FAILURES) > 32:  # unbounded distinct messages must not grow the set forever
        _LOGGED_FAILURES.clear()
    _LOGGED_FAILURES.add(key)
    logger.error(
        "portfolio SSE %s failed (stream degrades and retries): %s",
        where, key[1], exc_info=exc,
    )


def _sse_data(payload: Any) -> str:
    return f"data: {json.dumps(to_json_safe(payload), allow_nan=False)}\n\n"


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
        except Exception as exc:
            _log_stream_failure_once("subscription loop", exc)
            await asyncio.sleep(1)
            yield await _snapshot_event()


async def _channel_events(
    request: Request, channels: tuple[str, ...]
) -> AsyncIterator[Any]:
    """Multiplex broadcaster channels: yields each payload as it arrives, and
    ``_KEEP_ALIVE`` once per idle window.

    The pending ``__anext__`` tasks are HELD across timeouts — ``asyncio.wait``
    leaves them running on timeout, where ``wait_for`` would cancel into the
    subscriber generator and finalize it (the defect that closed
    ``/stream/executions`` after its first idle 15s window).
    """
    subscribers = [broadcaster.subscribe(channel) for channel in channels]
    tasks = {asyncio.create_task(sub.__anext__()): sub for sub in subscribers}
    try:
        while True:
            if await request.is_disconnected():
                return

            done, _ = await asyncio.wait(
                tasks.keys(), timeout=_IDLE_TIMEOUT_S, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                yield _KEEP_ALIVE
                continue

            for task in done:
                subscriber = tasks.pop(task)
                try:
                    payload = task.result()
                except StopAsyncIteration:
                    return
                except Exception as exc:
                    _log_stream_failure_once("subscriber pull", exc)
                    return
                yield payload
                tasks[asyncio.create_task(subscriber.__anext__())] = subscriber
    finally:
        for task in tasks:
            task.cancel()


async def _subscribed_snapshots(request: Request) -> AsyncIterator[str]:
    async for payload in _channel_events(request, _PORTFOLIO_CHANNELS):
        if payload is _KEEP_ALIVE:
            yield ": keep-alive\n\n"
        yield await _snapshot_event()


@router.get("/stream/portfolio")
async def stream_portfolio(request: Request) -> StreamingResponse:
    return StreamingResponse(_stream_snapshot_events(request), media_type="text/event-stream")


@router.get("/stream/executions")
async def stream_executions(request: Request) -> StreamingResponse:
    """Push-only stream of raw IBKR fills as they arrive."""

    async def gen():
        async for payload in _channel_events(request, ("executions",)):
            if payload is _KEEP_ALIVE:
                yield ": keep-alive\n\n"
            else:
                yield _sse_data(payload)

    return StreamingResponse(gen(), media_type="text/event-stream")

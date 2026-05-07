"""Thread-safe pub/sub used to fan IBKR events out to SSE subscribers."""
from __future__ import annotations

import asyncio
import threading
from typing import Any, AsyncIterator, Dict, Set


class Broadcaster:
    """Channel-based pub/sub.

    - ``publish`` / ``publish_threadsafe`` enqueue a payload onto every subscriber's queue.
    - ``subscribe`` yields payloads as an async generator suitable for an SSE endpoint.

    Subscribers are per-(channel, Queue). A slow subscriber drops its oldest message rather
    than blocking the publisher (bounded queue).
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._subs: Dict[str, Set[asyncio.Queue]] = {}
        # Event loop on which the subscriber queues were created. We use this loop for
        # thread-safe puts from the IBKR worker thread.
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        # When rebinding to a new loop (after IBKR reconnect), clear stale subscriber
        # queues that were created on the old loop — they can never receive messages.
        with self._lock:
            self._subs.clear()
        self._loop = loop

    def _get_or_create(self, channel: str) -> Set[asyncio.Queue]:
        subs = self._subs.get(channel)
        if subs is None:
            subs = set()
            self._subs[channel] = subs
        return subs

    async def subscribe(self, channel: str) -> AsyncIterator[Any]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        with self._lock:
            self._get_or_create(channel).add(queue)
        try:
            while True:
                payload = await queue.get()
                yield payload
        finally:
            with self._lock:
                subs = self._subs.get(channel)
                if subs is not None:
                    subs.discard(queue)

    def publish(self, channel: str, payload: Any) -> None:
        with self._lock:
            subs = list(self._subs.get(channel, ()))
        for q in subs:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass

    def publish_threadsafe(self, channel: str, payload: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self.publish, channel, payload)


broadcaster = Broadcaster()

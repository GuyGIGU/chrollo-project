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

    Loop ownership: queues live where their consumers live. The publish loop is
    the SERVER's, captured lazily from the first subscriber's running loop —
    never the IBKR worker thread's (asyncio queues are not thread-safe, and the
    old bind-to-IB-loop scheme both orphaned every stream open at Connect click
    and woke server-loop queues cross-thread).
    """

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._subs: Dict[str, Set[asyncio.Queue]] = {}
        # Event loop the subscriber queues live on (the server's), captured from
        # the first subscriber. publish_threadsafe hops onto it from any thread.
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_or_create(self, channel: str) -> Set[asyncio.Queue]:
        subs = self._subs.get(channel)
        if subs is None:
            subs = set()
            self._subs[channel] = subs
        return subs

    async def subscribe(self, channel: str) -> AsyncIterator[Any]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        loop = asyncio.get_running_loop()
        with self._lock:
            # Latest subscriber's loop wins — in production every subscriber
            # runs on the one uvicorn loop, so this is a stable capture.
            self._loop = loop
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
        dead = []
        for q in subs:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(payload)
                except Exception:
                    pass
            except Exception:
                # A queue whose consumer's loop is gone can never drain — drop
                # just that queue, never the whole subscriber set.
                dead.append(q)
        if dead:
            with self._lock:
                live = self._subs.get(channel)
                if live is not None:
                    for q in dead:
                        live.discard(q)

    def publish_threadsafe(self, channel: str, payload: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            loop.call_soon_threadsafe(self.publish, channel, payload)
        except RuntimeError:
            # Loop shut down between the check and the call — nothing to wake.
            pass


broadcaster = Broadcaster()

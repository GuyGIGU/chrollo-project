"""Portfolio SSE stream lifecycle + broadcaster loop ownership (council
2026-08-22, Ramirez F1/F2/F3).

F1: an idle keep-alive window must never finalize the subscriber generator —
the pending ``__anext__`` task is held across ``asyncio.wait`` timeouts (the
old ``wait_for`` cancelled into the generator and closed /stream/executions
after its first idle 15s).
F2: the degrade-and-retry catches log loudly, once per distinct failure.
F3: the broadcaster binds to the SUBSCRIBERS' loop (captured lazily from the
first subscriber), publishes cross-thread via call_soon_threadsafe, and drops
only a queue whose put fails — never the whole subscriber set.

Plain asyncio loops only; no backend boot, no uvicorn.
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.ibkr.broadcaster import Broadcaster  # noqa: E402
from webapp.backend.routers import portfolio_streams  # noqa: E402


async def _never_disconnected():
    return False


def _request():
    return SimpleNamespace(is_disconnected=_never_disconnected)


# ── F1: idle windows must not kill the subscription ─────────────────────────


def test_channel_events_survives_idle_windows(monkeypatch):
    bcast = Broadcaster()
    monkeypatch.setattr(portfolio_streams, "broadcaster", bcast)
    monkeypatch.setattr(portfolio_streams, "_IDLE_TIMEOUT_S", 0.05)

    async def scenario():
        gen = portfolio_streams._channel_events(_request(), ("executions",))
        events = [
            await asyncio.wait_for(gen.__anext__(), timeout=2),  # idle window 1
            await asyncio.wait_for(gen.__anext__(), timeout=2),  # idle window 2
        ]
        # A fill published AFTER two idle windows must still arrive — the old
        # wait_for path had already finalized the subscriber by now.
        bcast.publish("executions", {"symbol": "AAPL", "shares": 100})
        events.append(await asyncio.wait_for(gen.__anext__(), timeout=2))
        await gen.aclose()
        return events

    events = asyncio.run(scenario())
    assert events[0] is portfolio_streams._KEEP_ALIVE
    assert events[1] is portfolio_streams._KEEP_ALIVE
    assert events[2] == {"symbol": "AAPL", "shares": 100}


def test_subscribed_snapshots_idle_window_yields_keep_alive_then_snapshot(monkeypatch):
    """The folded helper preserves the portfolio stream's idle behavior:
    a comment line AND a fresh snapshot per idle window."""
    bcast = Broadcaster()
    monkeypatch.setattr(portfolio_streams, "broadcaster", bcast)
    monkeypatch.setattr(portfolio_streams, "_IDLE_TIMEOUT_S", 0.05)
    monkeypatch.setattr(
        portfolio_streams, "portfolio_snapshot_payload", lambda: {"connected": False}
    )

    async def scenario():
        gen = portfolio_streams._subscribed_snapshots(_request())
        first = await asyncio.wait_for(gen.__anext__(), timeout=2)
        second = await asyncio.wait_for(gen.__anext__(), timeout=2)
        await gen.aclose()
        return first, second

    first, second = asyncio.run(scenario())
    assert first == ": keep-alive\n\n"
    assert second.startswith("data: ")
    assert '"connected": false' in second


# ── F2: degrade loudly, once per distinct failure ───────────────────────────


def test_stream_failures_log_once_per_distinct_failure(caplog):
    portfolio_streams._LOGGED_FAILURES.clear()
    try:
        with caplog.at_level(logging.ERROR, logger="chrollo.portfolio_streams"):
            portfolio_streams._log_stream_failure_once("subscription loop", RuntimeError("boom"))
            portfolio_streams._log_stream_failure_once("subscription loop", RuntimeError("boom"))
            portfolio_streams._log_stream_failure_once("subscriber pull", RuntimeError("boom"))

        records = [r for r in caplog.records if r.name == "chrollo.portfolio_streams"]
        assert len(records) == 2  # repeat of a seen failure stays quiet
        assert "RuntimeError: boom" in records[0].getMessage()
    finally:
        portfolio_streams._LOGGED_FAILURES.clear()


def test_subscriber_pull_failure_logs_loudly_then_degrades(monkeypatch, caplog):
    portfolio_streams._LOGGED_FAILURES.clear()

    async def boom_subscribe(channel):
        raise RuntimeError("subscribe blew up")
        yield  # noqa: E501 — marks this as an async generator function

    monkeypatch.setattr(
        portfolio_streams, "broadcaster", SimpleNamespace(subscribe=boom_subscribe)
    )

    async def scenario():
        gen = portfolio_streams._channel_events(_request(), ("executions",))
        return [event async for event in gen]

    try:
        with caplog.at_level(logging.ERROR, logger="chrollo.portfolio_streams"):
            events = asyncio.run(scenario())

        assert events == []  # generator ended cleanly (degrade), no payloads
        pulls = [r for r in caplog.records if "subscriber pull" in r.getMessage()]
        assert len(pulls) == 1
    finally:
        portfolio_streams._LOGGED_FAILURES.clear()


# ── F3: loop ownership — queues live where the consumers live ───────────────


def test_broadcaster_captures_the_subscriber_loop_and_delivers_cross_thread():
    """The Connect-click sequence: a stream is already open on the server loop
    when the IBKR worker thread starts publishing. The publish must hop onto
    the subscriber's loop and deliver — and the subscriber set must survive."""
    bcast = Broadcaster()

    async def scenario():
        gen = bcast.subscribe("portfolio")
        task = asyncio.get_running_loop().create_task(gen.__anext__())
        await asyncio.sleep(0)  # let the subscription register + capture the loop
        assert bcast._loop is asyncio.get_running_loop()

        worker = threading.Thread(
            target=bcast.publish_threadsafe, args=("portfolio", {"cash": 1.0})
        )
        worker.start()
        worker.join()

        payload = await asyncio.wait_for(task, timeout=2)
        assert len(bcast._subs["portfolio"]) == 1  # nothing wiped the queue
        await gen.aclose()
        return payload

    assert asyncio.run(scenario()) == {"cash": 1.0}


def test_publish_threadsafe_is_a_noop_before_any_subscriber():
    bcast = Broadcaster()
    bcast.publish_threadsafe("portfolio", {"x": 1})  # no loop yet — must not raise


def test_publish_drops_only_the_queue_whose_put_fails():
    bcast = Broadcaster()

    # Subscriber A: parked waiting on a loop that then dies (its queue's
    # waiter can never be woken — put raises into the dead-queue drop path).
    dead_loop = asyncio.new_event_loop()

    async def park():
        gen = bcast.subscribe("portfolio")
        task = asyncio.get_running_loop().create_task(gen.__anext__())
        await asyncio.sleep(0)
        return gen, task

    parked = dead_loop.run_until_complete(park())  # noqa: F841 — held alive on purpose
    dead_loop.close()
    assert len(bcast._subs["portfolio"]) == 1

    # Subscriber B on a live loop still receives; A's dead queue is dropped.
    async def scenario():
        gen = bcast.subscribe("portfolio")
        task = asyncio.get_running_loop().create_task(gen.__anext__())
        await asyncio.sleep(0)
        bcast.publish("portfolio", {"x": 1})
        payload = await asyncio.wait_for(task, timeout=2)
        assert len(bcast._subs["portfolio"]) == 1  # B only — A was dropped
        await gen.aclose()
        return payload

    assert asyncio.run(scenario()) == {"x": 1}
    assert len(bcast._subs["portfolio"]) == 0


def test_bind_loop_is_retired():
    """The orphaning API is gone: nothing may rebind the broadcaster onto the
    IBKR thread's loop or wipe the subscriber set wholesale."""
    assert not hasattr(Broadcaster, "bind_loop")

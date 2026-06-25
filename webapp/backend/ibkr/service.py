"""IBKR service — owns the ib_async client on a dedicated asyncio loop/thread.

Thread-safety model:
- One background thread hosts an asyncio event loop and the ib_async ``IB`` client.
- All ``ib.*`` calls are scheduled onto that loop via ``asyncio.run_coroutine_threadsafe``.
- IBKR push events update an in-memory snapshot under a lock; sync consumers read it.
- IBKR events that need a DB write are forwarded to a separate writer thread (see
  ``db_writer``) so SQLAlchemy sessions never touch the IB loop.

If ``ib_async`` is not installed or TWS is unavailable, the service reports
``connected=False`` and every getter returns an empty snapshot. This keeps the rest of
the app functional for users who don't have IBKR configured.

Resilience:
- A 30-second heartbeat ping (``reqCurrentTime``) keeps the IB Gateway socket alive and
  detects dead connections faster than passive ``isConnected()`` polling.
- On disconnect, the last-known snapshot is preserved with a ``stale`` flag so the
  webapp keeps showing data instead of empty tables.
- Old IB instances are properly torn down before reconnecting to prevent ghost event
  handlers.
- Error codes are classified (benign, connectivity, fatal) so normal IB chatter doesn't
  pollute logs or trigger false disconnects.
- Client ID conflict detection: if IB Gateway rejects our client ID (e.g. TradingView
  already took it), we auto-increment and retry.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from broker_config import settings
from .broadcaster import broadcaster
from .mapping import (
    execution_to_dict,
    order_to_dict,
    portfolio_item_to_dict,
    position_to_dict,
)

log = logging.getLogger(__name__)

try:
    from ib_async import IB, util  # type: ignore
    _IB_AVAILABLE = True
except Exception:  # pragma: no cover - absence is a soft-fail
    IB = None  # type: ignore
    util = None  # type: ignore
    _IB_AVAILABLE = False


# ── Constants ────────────────────────────────────────────────────
# Benign IB error codes (market-data-farm status messages)
_BENIGN_ERRORS = {2104, 2106, 2158, 2108, 2100, 2119, 2137}

# Connectivity error codes: don't treat as fatal; the supervisor handles reconnect
_CONNECTIVITY_ERRORS = {
    1100,  # Connectivity between IB and TWS has been lost
    1101,  # Connectivity restored — data lost
    1102,  # Connectivity restored — data maintained
    2110,  # Connectivity between TWS and server is broken
}

# Client ID already in use
_CLIENT_ID_IN_USE = {326}

# Heartbeat interval in seconds
_HEARTBEAT_INTERVAL = 30

# IB Gateway daily restart window (UTC) — 03:45–04:00 UTC = 23:45–00:00 ET
_DAILY_RESTART_HOUR_UTC = 3
_DAILY_RESTART_MINUTE_START = 45


def _is_daily_restart_window() -> bool:
    """Return True if we're in the IB Gateway daily restart window."""
    now = datetime.now(timezone.utc)
    if now.hour == _DAILY_RESTART_HOUR_UTC and now.minute >= _DAILY_RESTART_MINUTE_START:
        return True
    if now.hour == (_DAILY_RESTART_HOUR_UTC + 1) % 24 and now.minute < 5:
        return True
    return False


@dataclass
class IBKRSnapshot:
    connected: bool = False
    mode: str = "live"
    client: str = "tws"
    host: str = ""
    port: int = 0
    client_id: int = 0
    last_update: float = 0.0
    last_error: Optional[str] = None
    stale: bool = False
    daily_restart: bool = False
    session_competition: bool = False

    account_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    positions: List[Dict[str, Any]] = field(default_factory=list)
    portfolio: List[Dict[str, Any]] = field(default_factory=list)
    open_orders: List[Dict[str, Any]] = field(default_factory=list)
    recent_executions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "connected": self.connected,
            "mode": self.mode,
            "client": self.client,
            "host": self.host,
            "port": self.port,
            "client_id": self.client_id,
            "last_update": self.last_update,
            "last_error": self.last_error,
            "stale": self.stale,
            "daily_restart": self.daily_restart,
            "session_competition": self.session_competition,
            "account_summary": self.account_summary,
            "positions": list(self.positions),
            "portfolio": list(self.portfolio),
            "open_orders": list(self.open_orders),
            "recent_executions": list(self.recent_executions),
        }


class IBKRService:
    """Singleton IBKR service. Acquire via :func:`get_ibkr_service`."""

    _instance: Optional["IBKRService"] = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._snapshot = IBKRSnapshot(
            mode=settings.ibkr_mode,
            client=settings.ibkr_client,
            host=settings.ibkr_host,
            port=settings.ibkr_port,
            client_id=settings.ibkr_client_id,
        )
        self._snap_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ib: Optional[Any] = None
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._exec_listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._pending_commission: Dict[str, Any] = {}
        # Track connection attempts for client ID auto-increment
        self._effective_client_id: int = settings.ibkr_client_id
        self._client_id_conflict: bool = False
        # Session competition detection: timestamps of recent disconnects
        self._disconnect_times: List[float] = []
        self._session_competition: bool = False
        self._paused: bool = False

    # ─── public API ──────────────────────────────────────────────
    @classmethod
    def instance(cls) -> "IBKRService":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def add_execution_listener(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback invoked for every execution (called from the IB thread).

        Keep the callback fast — offload any DB work to a queue.
        """
        self._exec_listeners.append(fn)

    def is_available(self) -> bool:
        return _IB_AVAILABLE

    def is_connected(self) -> bool:
        with self._snap_lock:
            return self._snapshot.connected

    def is_paused(self) -> bool:
        return self._paused

    def snapshot(self) -> Dict[str, Any]:
        with self._snap_lock:
            return self._snapshot.to_dict()

    def resume(self) -> None:
        """Manually resume auto-reconnect after session competition pause.

        Call this from the /ibkr/reconnect endpoint when the user is ready.
        """
        self._paused = False
        self._session_competition = False
        self._disconnect_times.clear()
        with self._snap_lock:
            self._snapshot.session_competition = False
            self._snapshot.last_error = None
        log.info("IBKR auto-reconnect resumed by user")
        broadcaster.publish_threadsafe("ibkr_status", self.snapshot())

    def get_account_summary(self) -> Dict[str, Dict[str, Any]]:
        with self._snap_lock:
            return dict(self._snapshot.account_summary)

    def get_positions(self) -> List[Dict[str, Any]]:
        with self._snap_lock:
            # portfolio is richer (includes mkt price/value); fall back to plain positions
            return list(self._snapshot.portfolio or self._snapshot.positions)

    def get_open_orders(self) -> List[Dict[str, Any]]:
        with self._snap_lock:
            return list(self._snapshot.open_orders)

    def get_recent_executions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._snap_lock:
            return list(self._snapshot.recent_executions[-limit:])

    def start(self, *, confirmed: bool = False) -> None:
        """Start the IBKR supervisor thread.

        ``confirmed=True`` represents a *deliberate, in-the-moment human
        confirmation* (a dashboard click that passed a "connect to real money?"
        dialog) and lets this one start bypass the live gate. It is intentionally
        NOT persisted, so a reboot / crash-restart still comes up broker-free.
        """
        if not _IB_AVAILABLE:
            log.warning("ib_async not installed — IBKR service will stay disconnected.")
            self._set_error("ib_async not installed")
            return
        if settings.ibkr_mode == "live" and not confirmed:
            log.warning(
                "IBKR mode=live requires a per-click Connect IBKR confirmation; "
                "refusing broker start without confirm=true."
            )
            self._set_error("live start blocked: runtime confirmation required")
            return
        if self._thread and self._thread.is_alive():
            if not self._stop_event.is_set():
                return
            # The old thread is currently dying (maybe stuck in connectAsync timeout).
            # Wait until it completely exits before spawning a new one.
            self._thread.join(timeout=10.0)

        # Reset client ID to configured value on fresh start
        self._effective_client_id = settings.ibkr_client_id
        self._client_id_conflict = False

        # Create a fresh event per thread so an abandoned thread doesn't wake back up
        stop_evt = threading.Event()
        self._stop_event = stop_evt
        self._ready_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run_loop, args=(stop_evt,), name="ibkr-loop", daemon=True
        )
        self._thread.start()
        # Don't block FastAPI startup if TWS is down
        self._ready_event.wait(timeout=0.5)

    def stop(self) -> None:
        self._stop_event.set()
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), loop).result(timeout=3)
            except Exception:  # pragma: no cover
                log.exception("IBKR shutdown failed")
        if self._thread:
            self._thread.join(timeout=3)
        self._mark_disconnected("manual disconnect")

    def apply_settings(self) -> None:
        """Sync snapshot metadata (mode/host/port/client_id) from broker_config.settings.

        Call after ``broker_config.set_mode()`` while the service is stopped; the next
        ``start()`` will connect using the fresh values.
        """
        with self._snap_lock:
            self._snapshot.mode = settings.ibkr_mode
            self._snapshot.client = settings.ibkr_client
            self._snapshot.host = settings.ibkr_host
            self._snapshot.port = settings.ibkr_port
            self._snapshot.client_id = settings.ibkr_client_id
            self._snapshot.last_error = None
        broadcaster.publish_threadsafe("ibkr_status", self.snapshot())

    # ─── internals ───────────────────────────────────────────────
    def _run_loop(self, stop_event: threading.Event) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        broadcaster.bind_loop(loop)
        self._ready_event.set()
        try:
            loop.run_until_complete(self._supervisor(stop_event))
        except Exception:  # pragma: no cover
            log.exception("IBKR loop crashed")
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()
            self._loop = None

    def _record_disconnect(self) -> None:
        """Track disconnect timestamps to detect session competition.

        If we see 3+ disconnects within 60s, another platform (e.g. TradingView)
        is fighting us for the IBKR login session. We should back off.
        """
        now = time.time()
        self._disconnect_times.append(now)
        # Keep only the last 60 seconds of disconnect events
        cutoff = now - 60
        self._disconnect_times = [t for t in self._disconnect_times if t > cutoff]
        if len(self._disconnect_times) >= 3:
            self._session_competition = True
            log.warning(
                "Session competition detected — %d disconnects in 60s. "
                "Another platform (TradingView?) is fighting for the IBKR session. "
                "Pausing auto-reconnect to avoid kicking the other platform.",
                len(self._disconnect_times),
            )

    async def _supervisor(self, stop_event: threading.Event) -> None:
        """Connect + keep connection alive with exponential backoff.

        - Heartbeat ping every 30s to keep IB Gateway socket alive
        - Detects client ID conflicts and auto-increments
        - Detects daily restart window and sets a flag for the frontend
        - Detects session competition (rapid disconnects) and pauses reconnect
          so we don't keep stealing the session from TradingView
        """
        backoff = 1.0
        while not stop_event.is_set():
            # If paused (session competition), wait for user to manually resume
            if self._paused:
                await asyncio.sleep(2.0)
                continue

            # Check for daily restart window
            if _is_daily_restart_window():
                self._mark_disconnected("daily_restart")
                log.info("IB Gateway daily restart window — waiting 60s before reconnecting")
                await asyncio.sleep(60)
                continue

            # Session competition detected — pause and let the other platform have it
            if self._session_competition:
                self._paused = True
                self._mark_disconnected("session_competition")
                log.warning(
                    "Auto-reconnect paused — use the dashboard Reconnect button "
                    "or POST /ibkr/reconnect when TradingView is done."
                )
                continue

            try:
                await self._connect_and_prime()
                backoff = 1.0  # reset backoff on successful connection
                # Clear disconnect history on successful stable connection
                self._disconnect_times.clear()

                # ── Heartbeat loop: stay connected and keep the socket alive ──
                heartbeat_counter = 0
                while not stop_event.is_set() and self._ib and self._ib.isConnected():
                    await asyncio.sleep(1.0)
                    heartbeat_counter += 1
                    if heartbeat_counter >= _HEARTBEAT_INTERVAL:
                        heartbeat_counter = 0
                        try:
                            self._ib.reqCurrentTime()
                        except Exception:
                            log.warning("Heartbeat ping failed — connection likely dead")
                            break

                if self._ib and not self._ib.isConnected() and not stop_event.is_set():
                    self._record_disconnect()
                    reason = "daily_restart" if _is_daily_restart_window() else "disconnected"
                    log.warning("IBKR disconnected (%s); will retry", reason)
                    self._mark_disconnected(reason)

            except Exception as e:  # pragma: no cover - depends on TWS state
                if stop_event.is_set():
                    break

                err_str = str(e)
                self._record_disconnect()

                # Client ID conflict: TradingView or another app took our client ID
                if self._client_id_conflict or "client id" in err_str.lower():
                    self._effective_client_id = self._effective_client_id + 1
                    self._client_id_conflict = False
                    log.warning(
                        "Client ID conflict detected — retrying with clientId=%d",
                        self._effective_client_id,
                    )
                    await asyncio.sleep(1.0)
                    continue

                log.warning("IBKR connect failed: %s", e)
                self._mark_disconnected(err_str)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _connect_and_prime(self) -> None:
        assert IB is not None

        # ── Cleanly dispose of any previous IB instance ──
        old_ib = self._ib
        if old_ib is not None:
            self._ib = None
            try:
                if old_ib.isConnected():
                    old_ib.disconnect()
            except Exception:
                pass

        self._ib = IB()
        self._wire_events(self._ib)
        await self._ib.connectAsync(
            settings.ibkr_host,
            settings.ibkr_port,
            clientId=self._effective_client_id,
            readonly=True,
            timeout=8,
        )

        log.info(
            "Connected to IBKR %s:%d (clientId=%d, mode=%s)",
            settings.ibkr_host,
            settings.ibkr_port,
            self._effective_client_id,
            settings.ibkr_mode,
        )

        # Subscribe to streaming updates
        self._ib.reqMarketDataType(3)  # delayed if no real-time entitlement (safe default)
        try:
            self._ib.reqPositions()
        except Exception:
            pass
        try:
            # account_ values are needed for summary; empty string = all accounts
            self._ib.reqAccountUpdates(True, "")
        except Exception:
            pass
        try:
            self._ib.reqAllOpenOrders()
        except Exception:
            pass
        try:
            # Back-fill today's executions so a reconnect doesn't lose anything
            await self._ib.reqExecutionsAsync()
        except Exception:
            pass

        with self._snap_lock:
            self._snapshot.connected = True
            self._snapshot.stale = False
            self._snapshot.daily_restart = False
            self._snapshot.last_error = None
            self._snapshot.last_update = time.time()
            self._snapshot.client_id = self._effective_client_id
        broadcaster.publish_threadsafe("ibkr_status", self.snapshot())

    def _wire_events(self, ib: Any) -> None:
        ib.disconnectedEvent += lambda: self._mark_disconnected("disconnected event")
        ib.errorEvent += self._on_error

        ib.accountValueEvent += self._on_account_value
        ib.positionEvent += self._on_position
        ib.updatePortfolioEvent += self._on_portfolio
        ib.openOrderEvent += self._on_open_order
        ib.orderStatusEvent += self._on_order_status
        ib.execDetailsEvent += self._on_exec_details
        ib.commissionReportEvent += self._on_commission

    async def _shutdown(self) -> None:
        ib = self._ib
        self._ib = None
        if ib and ib.isConnected():
            try:
                await asyncio.wait_for(ib.disconnectAsync(), timeout=2.5)
            except Exception:
                try:
                    ib.disconnect()
                except Exception:
                    pass

    def _mark_disconnected(self, err: str) -> None:
        is_daily = err == "daily_restart" or _is_daily_restart_window()
        is_competition = err == "session_competition" or self._session_competition
        with self._snap_lock:
            self._snapshot.connected = False
            self._snapshot.stale = True
            self._snapshot.daily_restart = is_daily
            self._snapshot.session_competition = is_competition
            self._snapshot.last_error = err
            self._snapshot.last_update = time.time()
            # NOTE: We intentionally do NOT clear account_summary, positions,
            # portfolio, open_orders, or recent_executions here.
            # The last-known data is preserved so the frontend keeps showing it
            # with a "stale" indicator instead of empty tables.
        broadcaster.publish_threadsafe("ibkr_status", self.snapshot())

    def _set_error(self, err: str) -> None:
        with self._snap_lock:
            self._snapshot.last_error = err
            self._snapshot.last_update = time.time()

    # ─── IB event handlers (run on the IB loop thread) ───────────
    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Any) -> None:
        # Benign market-data-farm / connectivity status messages
        if errorCode in _BENIGN_ERRORS:
            return

        # Connectivity lost/restored — let the supervisor handle reconnection
        if errorCode in _CONNECTIVITY_ERRORS:
            if errorCode == 1100:
                log.warning("IBKR connectivity lost (1100): %s", errorString)
            elif errorCode in {1101, 1102}:
                log.info("IBKR connectivity restored (%d): %s", errorCode, errorString)
            else:
                log.warning("IBKR connectivity issue (%d): %s", errorCode, errorString)
            return

        # Client ID already in use — set flag so supervisor can auto-increment
        if errorCode in _CLIENT_ID_IN_USE:
            log.warning(
                "Client ID %d already in use (error %d) — another platform "
                "(e.g. TradingView) likely has it. Will auto-increment.",
                self._effective_client_id,
                errorCode,
            )
            self._client_id_conflict = True
            return

        log.warning("IBKR error %s: %s", errorCode, errorString)

    def _on_account_value(self, av: Any) -> None:
        key = getattr(av, "tag", None)
        if not key:
            return
        val = getattr(av, "value", None)
        currency = getattr(av, "currency", None)
        account = getattr(av, "account", None)
        with self._snap_lock:
            bucket = self._snapshot.account_summary.setdefault(account or "", {})
            bucket[key] = {"value": val, "currency": currency}
            self._snapshot.last_update = time.time()
        broadcaster.publish_threadsafe("portfolio", self.snapshot())

    def _on_position(self, position: Any) -> None:
        d = position_to_dict(position)
        with self._snap_lock:
            # Replace existing entry for (account, symbol)
            self._snapshot.positions = [
                p for p in self._snapshot.positions
                if not (p.get("account") == d.get("account") and p.get("symbol") == d.get("symbol"))
            ]
            if d.get("quantity"):
                self._snapshot.positions.append(d)
            self._snapshot.last_update = time.time()

    def _on_portfolio(self, item: Any) -> None:
        d = portfolio_item_to_dict(item)
        with self._snap_lock:
            self._snapshot.portfolio = [
                p for p in self._snapshot.portfolio
                if not (p.get("account") == d.get("account") and p.get("symbol") == d.get("symbol"))
            ]
            if d.get("quantity"):
                self._snapshot.portfolio.append(d)
            self._snapshot.last_update = time.time()
        broadcaster.publish_threadsafe("portfolio", self.snapshot())

    def _on_open_order(self, trade: Any) -> None:
        d = order_to_dict(trade)
        with self._snap_lock:
            self._snapshot.open_orders = [
                o for o in self._snapshot.open_orders
                if o.get("order_id") != d.get("order_id")
            ]
            self._snapshot.open_orders.append(d)
            self._snapshot.last_update = time.time()
        broadcaster.publish_threadsafe("orders", d)

    def _on_order_status(self, trade: Any) -> None:
        self._on_open_order(trade)

    def _on_exec_details(self, trade: Any, fill: Any) -> None:
        exec_obj = getattr(fill, "execution", None)
        contract = getattr(fill, "contract", None) or getattr(trade, "contract", None)
        commission_report = getattr(fill, "commissionReport", None)
        if exec_obj is None:
            return
        d = execution_to_dict(exec_obj, contract, commission_report)
        with self._snap_lock:
            self._snapshot.recent_executions.append(d)
            if len(self._snapshot.recent_executions) > 500:
                self._snapshot.recent_executions = self._snapshot.recent_executions[-500:]
            self._snapshot.last_update = time.time()
        broadcaster.publish_threadsafe("executions", d)
        for fn in list(self._exec_listeners):
            try:
                fn(d)
            except Exception:
                log.exception("execution listener failed")

    def _on_commission(self, trade: Any, fill: Any, report: Any) -> None:
        # A commission report may arrive slightly after the exec. Patch the last matching entry.
        exec_id = getattr(getattr(fill, "execution", None), "execId", None)
        if not exec_id:
            return
        patched_entry = None
        with self._snap_lock:
            for e in reversed(self._snapshot.recent_executions):
                if e.get("exec_id") == exec_id:
                    try:
                        e["commission"] = float(getattr(report, "commission", 0) or 0)
                    except Exception:
                        pass
                    try:
                        e["realized_pnl"] = float(getattr(report, "realizedPNL", 0) or 0)
                    except Exception:
                        pass
                    patched_entry = dict(e)
                    break
        # Forward late commission data to listeners (e.g. auto_import DB writer)
        if patched_entry:
            for fn in list(self._exec_listeners):
                try:
                    fn(patched_entry)
                except Exception:
                    log.exception("execution listener failed (commission patch)")


def get_ibkr_service() -> IBKRService:
    return IBKRService.instance()

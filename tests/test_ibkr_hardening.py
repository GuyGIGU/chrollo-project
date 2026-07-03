"""IBKR runtime hardening guards (quality-doctrine WP-B).

Pins the fixes for the connection-churn class of defects:
- the heartbeat pings via the *async* time request under a real timeout
  (the sync variant re-entered the running IB loop and read as a dead
  connection every 30s);
- the post-connect prime requests use the async API variants and actually
  populate the snapshot (the sync/mis-signatured calls silently no-opped
  behind except:pass, leaving the Open Orders pane empty);
- snapshot reads are isolated from IB-thread mutation (deep copy);
- reconnect churn is visible via telemetry;
- and the house law "Chrollo never places orders" is structural: the order
  API is stripped from every IB instance, and zero call sites exist repo-wide.
"""
import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

from webapp.backend.ibkr import service as ibkr_service


# ── read-only house law ──────────────────────────────────────────


def test_forbidden_order_api_raises():
    ib = SimpleNamespace()
    ibkr_service._forbid_order_api(ib)
    for name in ibkr_service._FORBIDDEN_ORDER_METHODS:
        try:
            getattr(ib, name)()
            raise AssertionError(f"{name} did not raise")
        except PermissionError:
            pass


def test_no_order_api_call_sites_repo_wide():
    """Zero call sites of the IB order-entry API anywhere in the repo,
    frontend included. The blocklist tuple in service.py names the methods
    without parentheses, so it does not trip this scan."""
    patterns = [name + "(" for name in ibkr_service._FORBIDDEN_ORDER_METHODS]
    skip_dirs = {
        ".git", "node_modules", "__pycache__", "dist", "build",
        ".claude", "venv", ".venv", ".pytest_cache",
    }
    offenders = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if not fn.endswith((".py", ".js", ".jsx")):
                continue
            path = Path(dirpath) / fn
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pat in patterns:
                if pat in text:
                    offenders.append(f"{path.relative_to(ROOT)}: {pat}")
    assert offenders == [], f"order-API call sites found: {offenders}"


# ── heartbeat ────────────────────────────────────────────────────


def test_heartbeat_ok_awaits_the_async_time_request():
    svc = ibkr_service.IBKRService()
    calls = []

    async def req_current_time_async():
        calls.append("ping")
        return "2026-07-03"

    svc._ib = SimpleNamespace(reqCurrentTimeAsync=req_current_time_async)
    assert asyncio.run(svc._heartbeat_ok()) is True
    assert calls == ["ping"]


def test_heartbeat_times_out_on_dead_socket(monkeypatch):
    monkeypatch.setattr(ibkr_service, "_HEARTBEAT_TIMEOUT", 0.05)
    svc = ibkr_service.IBKRService()

    async def hang():
        await asyncio.sleep(60)

    svc._ib = SimpleNamespace(reqCurrentTimeAsync=hang)
    assert asyncio.run(svc._heartbeat_ok()) is False


# ── snapshot isolation ───────────────────────────────────────────


def test_snapshot_account_summary_is_isolated_from_ib_thread_mutation():
    svc = ibkr_service.IBKRService()
    svc._snapshot.account_summary["U1"] = {
        "NetLiquidation": {"value": "100", "currency": "USD"},
    }

    snap = svc.snapshot()
    summary = svc.get_account_summary()
    # Simulate the IB thread mutating the live bucket after the read.
    svc._snapshot.account_summary["U1"]["BuyingPower"] = {"value": "5", "currency": "USD"}

    assert "BuyingPower" not in snap["account_summary"]["U1"]
    assert "BuyingPower" not in summary["U1"]


# ── connect-and-prime ────────────────────────────────────────────


class _Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self


class _FakeIB:
    """Records which API variants _connect_and_prime uses."""

    def __init__(self):
        self.calls = []
        for name in (
            "disconnectedEvent", "errorEvent", "accountValueEvent",
            "positionEvent", "updatePortfolioEvent", "openOrderEvent",
            "orderStatusEvent", "execDetailsEvent", "commissionReportEvent",
        ):
            setattr(self, name, _Event())

    def isConnected(self):
        return True

    async def connectAsync(self, host, port, clientId=0, readonly=False, timeout=0):
        self.calls.append(("connectAsync", readonly))

    def reqMarketDataType(self, data_type):
        self.calls.append(("reqMarketDataType", data_type))

    async def reqPositionsAsync(self):
        self.calls.append(("reqPositionsAsync",))
        return []

    async def reqAccountUpdatesAsync(self, account):
        self.calls.append(("reqAccountUpdatesAsync", account))

    async def reqAllOpenOrdersAsync(self):
        self.calls.append(("reqAllOpenOrdersAsync",))
        return [SimpleNamespace(
            order=SimpleNamespace(
                orderId=7, permId=11, account="U1", action="SELL",
                orderType="STP", totalQuantity=100.0, lmtPrice=None, auxPrice=50.0,
            ),
            contract=SimpleNamespace(secType="STK", symbol="AAPL", localSymbol=""),
            orderStatus=SimpleNamespace(
                status="PreSubmitted", filled=0.0, remaining=100.0, avgFillPrice=None,
            ),
        )]

    async def reqExecutionsAsync(self):
        self.calls.append(("reqExecutionsAsync",))
        return []


def test_connect_and_prime_uses_async_variants_and_blocks_orders(monkeypatch):
    monkeypatch.setattr(ibkr_service, "IB", _FakeIB)
    monkeypatch.setattr(
        ibkr_service.broadcaster, "publish_threadsafe", lambda *a, **k: None
    )
    svc = ibkr_service.IBKRService()

    asyncio.run(svc._connect_and_prime())

    call_names = [c[0] for c in svc._ib.calls]
    assert ("connectAsync", True) in svc._ib.calls  # readonly=True, always
    assert "reqPositionsAsync" in call_names
    assert ("reqAccountUpdatesAsync", "") in svc._ib.calls  # 2.1.0 signature
    assert "reqAllOpenOrdersAsync" in call_names
    assert "reqExecutionsAsync" in call_names

    snap = svc.snapshot()
    # The startup order fetch primes the Open Orders pane (readonly connects
    # don't get it automatically).
    assert [o["order_id"] for o in snap["open_orders"]] == [7]
    # Telemetry: the successful connect is counted and stamped.
    assert snap["reconnect_count"] == 1
    assert snap["last_connect_at"] is not None
    # The order-entry API is structurally disabled on the constructed instance.
    for name in ibkr_service._FORBIDDEN_ORDER_METHODS:
        try:
            getattr(svc._ib, name)()
            raise AssertionError(f"{name} did not raise")
        except PermissionError:
            pass

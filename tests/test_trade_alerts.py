import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import models
from services import health, scheduler, trade_alerts


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    models.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield Session
    finally:
        models.Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clear_alert_state():
    trade_alerts.reset_alert_state()
    yield
    trade_alerts.reset_alert_state()


def add_trade(session_factory, **overrides):
    payload = {
        "opening_date": "2026-06-01",
        "direction": "LONG",
        "ticker": "MSFT",
        "entry_price": 100,
        "stop_loss": 90,
        "quantity": 10,
        "pnl": None,
        "closing_date": None,
    }
    payload.update(overrides)
    db = session_factory()
    try:
        row = models.TradeLog(**payload)
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def run_sweep(session_factory, price, messages):
    return trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": price},
        notifier=lambda text: messages.append(text) or True,
        cooldown_minutes=0,
    )


def test_sweep_status_records_counts_for_successful_run(session_factory):
    add_trade(session_factory)
    messages = []

    run_sweep(session_factory, 95, messages)
    status = trade_alerts.get_trade_alert_status()

    assert status["status"] == "ok"
    assert status["enabled"] is True
    assert status["market_window"] is True
    assert status["open_trades_checked"] == 1
    assert status["quotes_found"] == 1
    assert status["alerts_sent"] == 1
    assert status["last_error"] is None
    assert status["last_checked_at"] is not None


def test_stop_alerts_escalate_and_suppress_same_band_repeats(session_factory):
    add_trade(session_factory)
    messages = []

    assert run_sweep(session_factory, 95, messages) == 1
    assert "0.50R" in messages[-1]
    assert run_sweep(session_factory, 95, messages) == 0
    assert run_sweep(session_factory, 92, messages) == 1
    assert "0.20R" in messages[-1]
    assert run_sweep(session_factory, 89, messages) == 1
    assert "through stop" in messages[-1]
    assert run_sweep(session_factory, 97, messages) == 0
    assert run_sweep(session_factory, 95, messages) == 1

    assert len(messages) == 4


def test_target_near_resets_after_trade_moves_away(session_factory):
    add_trade(session_factory, t1_price=110)
    messages = []

    assert run_sweep(session_factory, 108, messages) == 1
    assert "near T1" in messages[-1]
    assert run_sweep(session_factory, 108, messages) == 0
    assert run_sweep(session_factory, 105, messages) == 0
    assert run_sweep(session_factory, 108, messages) == 1

    assert len(messages) == 2


def test_target_hit_fires_once_per_new_reached_target(session_factory):
    add_trade(session_factory, t1_price=110, t2_price=120)
    messages = []

    assert run_sweep(session_factory, 112, messages) == 1
    assert "hit T1" in messages[-1]
    assert run_sweep(session_factory, 112, messages) == 0
    assert run_sweep(session_factory, 121, messages) == 1
    assert "hit T2" in messages[-1]


def test_failed_notifier_does_not_burn_stop_dedupe_state(session_factory):
    add_trade(session_factory)
    attempted = []
    delivered = []

    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 95},
        notifier=lambda text: attempted.append(text) and False,
        cooldown_minutes=0,
    ) == 0

    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 95},
        notifier=lambda text: delivered.append(text) or True,
        cooldown_minutes=0,
    ) == 1

    assert len(attempted) == 1
    assert len(delivered) == 1
    assert "0.50R" in delivered[0]


def test_notifier_exception_does_not_burn_target_hit_state(session_factory):
    add_trade(session_factory, t1_price=110)
    delivered = []

    def failing_notifier(_text):
        raise RuntimeError("webhook down")

    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 112},
        notifier=failing_notifier,
        cooldown_minutes=0,
    ) == 0

    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 112},
        notifier=lambda text: delivered.append(text) or True,
        cooldown_minutes=0,
    ) == 1

    assert len(delivered) == 1
    assert "hit T1" in delivered[0]


def test_cooldown_suppression_does_not_burn_reentry_state(session_factory):
    add_trade(session_factory)
    messages = []

    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 95},
        notifier=lambda text: messages.append(text) or True,
        cooldown_minutes=5,
        now_fn=lambda: 0,
    ) == 1
    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 100},
        notifier=lambda text: messages.append(text) or True,
        cooldown_minutes=5,
        now_fn=lambda: 10,
    ) == 0
    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 95},
        notifier=lambda text: messages.append(text) or True,
        cooldown_minutes=5,
        now_fn=lambda: 60,
    ) == 0
    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {"MSFT": 95},
        notifier=lambda text: messages.append(text) or True,
        cooldown_minutes=5,
        now_fn=lambda: 301,
    ) == 1

    assert len(messages) == 2


def test_no_stop_or_missing_quote_stays_silent(session_factory):
    add_trade(session_factory, stop_loss=None, t1_price=110)
    messages = []

    assert run_sweep(session_factory, 108, messages) == 0
    assert trade_alerts.run_trade_alert_sweep(
        session_factory=session_factory,
        quote_fn=lambda tickers: {},
        notifier=lambda text: messages.append(text) or True,
        cooldown_minutes=0,
    ) == 0
    assert messages == []


def test_trade_alert_window_is_regular_nyse_hours_only():
    ny = ZoneInfo("America/New_York")

    assert scheduler._is_trade_alert_window(datetime(2026, 6, 23, 10, 0, tzinfo=ny)) is True
    assert scheduler._is_trade_alert_window(datetime(2026, 6, 23, 8, 0, tzinfo=ny)) is False
    assert scheduler._is_trade_alert_window(datetime(2026, 6, 23, 16, 0, tzinfo=ny)) is False
    assert scheduler._is_trade_alert_window(datetime(2026, 1, 1, 10, 0, tzinfo=ny)) is False


def test_scheduler_records_disabled_trade_alert_sweep(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "load_core_settings",
        lambda: SimpleNamespace(TRADE_ALERTS_ENABLED=False),
    )

    scheduler.run_trade_alert_sweep_if_due()
    status = trade_alerts.get_trade_alert_status()

    assert status["status"] == "disabled"
    assert status["enabled"] is False
    assert status["market_window"] is False
    assert status["last_checked_at"] is not None


def test_scheduler_records_outside_market_hours_skip(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "load_core_settings",
        lambda: SimpleNamespace(TRADE_ALERTS_ENABLED=True),
    )
    monkeypatch.setattr(scheduler, "_is_trade_alert_window", lambda: False)
    monkeypatch.setattr(
        scheduler,
        "run_trade_alert_sweep",
        lambda: pytest.fail("sweep should not run outside market hours"),
    )

    scheduler.run_trade_alert_sweep_if_due()
    status = trade_alerts.get_trade_alert_status()

    assert status["status"] == "outside_market_hours"
    assert status["enabled"] is True
    assert status["market_window"] is False


def test_scheduler_records_trade_alert_sweep_error(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "load_core_settings",
        lambda: SimpleNamespace(TRADE_ALERTS_ENABLED=True),
    )
    monkeypatch.setattr(scheduler, "_is_trade_alert_window", lambda: True)

    def fail_sweep():
        raise RuntimeError("quote source exploded")

    monkeypatch.setattr(scheduler, "run_trade_alert_sweep", fail_sweep)

    scheduler.run_trade_alert_sweep_if_due()
    status = trade_alerts.get_trade_alert_status()

    assert status["status"] == "error"
    assert status["enabled"] is True
    assert status["market_window"] is True
    assert "quote source exploded" in status["last_error"]


def test_health_check_includes_trade_alert_status(monkeypatch):
    trade_alerts.record_trade_alert_skip("outside_market_hours", enabled=True, market_window=False)
    monkeypatch.setattr(
        health,
        "load_core_settings",
        lambda: SimpleNamespace(TRADE_ALERTS_ENABLED=True),
    )
    checks = {}

    health._add_trade_alerts_check(checks)

    assert checks["trade_alerts"]["ok"] is True
    assert checks["trade_alerts"]["configured_enabled"] is True
    assert checks["trade_alerts"]["status"] == "outside_market_hours"

"""Always-on stop/target alert sweep for open trades."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from collections.abc import Callable
from datetime import datetime, timezone

from database import SessionLocal
import models
from services.core_settings import load_core_settings
from services.live_quotes import fetch_live_quotes
from services.notify import post_webhook
from services.trade_risk import TargetRisk, TradeRisk, evaluate_open_trade

log = logging.getLogger("chrollo.trade_alerts")

_STOP_SEVERITY = {None: 0, "warning": 1, "danger": 2, "breached": 3}


@dataclass
class _TradeAlertMemory:
    stop_band: str | None = None
    target_near_label: str | None = None
    hit_targets: set[str] = field(default_factory=set)
    last_fired_at: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class _PendingAlert:
    message: str
    commit: Callable[[], None]


_ALERT_STATE: dict[str, _TradeAlertMemory] = {}
_STATUS_LOCK = threading.Lock()


@dataclass
class TradeAlertSweepStatus:
    status: str = "never_run"
    enabled: bool = False
    market_window: bool = False
    last_checked_at: str | None = None
    open_trades_checked: int = 0
    quotes_found: int = 0
    alerts_sent: int = 0
    last_error: str | None = None


_SWEEP_STATUS = TradeAlertSweepStatus()


def reset_alert_state() -> None:
    """Clear in-memory dedupe state. Intended for tests and service restarts."""
    _ALERT_STATE.clear()
    with _STATUS_LOCK:
        global _SWEEP_STATUS
        _SWEEP_STATUS = TradeAlertSweepStatus()


def get_trade_alert_status() -> dict:
    with _STATUS_LOCK:
        return asdict(_SWEEP_STATUS)


def record_trade_alert_skip(status: str, *, enabled: bool, market_window: bool) -> None:
    _record_sweep_status(
        status=status,
        enabled=enabled,
        market_window=market_window,
        open_trades_checked=0,
        quotes_found=0,
        alerts_sent=0,
        last_error=None,
    )


def record_trade_alert_error(error: Exception | str, *, enabled: bool = True, market_window: bool = True) -> None:
    _record_sweep_status(
        status="error",
        enabled=enabled,
        market_window=market_window,
        open_trades_checked=_SWEEP_STATUS.open_trades_checked,
        quotes_found=_SWEEP_STATUS.quotes_found,
        alerts_sent=0,
        last_error=str(error)[:300],
    )


def run_trade_alert_sweep(
    *,
    session_factory=SessionLocal,
    quote_fn: Callable[[list[str]], dict[str, float]] = fetch_live_quotes,
    notifier: Callable[[str], bool] = post_webhook,
    cooldown_minutes: float | None = None,
    now_fn: Callable[[], float] = time.time,
) -> int:
    """Evaluate open trades and send deduped stop/target webhook alerts."""
    db = session_factory()
    try:
        trades = _load_open_trades(db)
    finally:
        close = getattr(db, "close", None)
        if close:
            close()

    open_keys = {_trade_key(trade) for trade in trades}
    _prune_closed_trades(open_keys)
    if not trades:
        _record_sweep_status(
            status="ok",
            enabled=True,
            market_window=True,
            open_trades_checked=0,
            quotes_found=0,
            alerts_sent=0,
            last_error=None,
        )
        return 0

    tickers = sorted({_ticker_for(trade) for trade in trades if _ticker_for(trade)})
    quotes = quote_fn(tickers) or {}
    quotes_found = sum(1 for ticker in tickers if quotes.get(ticker) is not None)
    cooldown_minutes = _cooldown_minutes(cooldown_minutes)
    now = now_fn()
    sent_count = 0

    for trade in trades:
        ticker = _ticker_for(trade)
        if not ticker:
            continue
        price = quotes.get(ticker)
        if price is None:
            continue

        trade_key = _trade_key(trade)
        risk = evaluate_open_trade(trade, price)
        if risk is None:
            _ALERT_STATE.pop(trade_key, None)
            continue

        for alert in _pending_alerts_for_risk(risk, trade_key, cooldown_minutes, now):
            log.warning(alert.message)
            try:
                delivered = notifier(alert.message)
            except Exception:
                log.exception("trade alert notifier failed")
                delivered = False
            if delivered:
                alert.commit()
                sent_count += 1

    _record_sweep_status(
        status="ok",
        enabled=True,
        market_window=True,
        open_trades_checked=len(trades),
        quotes_found=quotes_found,
        alerts_sent=sent_count,
        last_error=None,
    )
    return sent_count


def _record_sweep_status(
    *,
    status: str,
    enabled: bool,
    market_window: bool,
    open_trades_checked: int,
    quotes_found: int,
    alerts_sent: int,
    last_error: str | None,
) -> None:
    with _STATUS_LOCK:
        _SWEEP_STATUS.status = status
        _SWEEP_STATUS.enabled = enabled
        _SWEEP_STATUS.market_window = market_window
        _SWEEP_STATUS.last_checked_at = datetime.now(timezone.utc).isoformat()
        _SWEEP_STATUS.open_trades_checked = open_trades_checked
        _SWEEP_STATUS.quotes_found = quotes_found
        _SWEEP_STATUS.alerts_sent = alerts_sent
        _SWEEP_STATUS.last_error = last_error


def _load_open_trades(db) -> list[models.TradeLog]:
    return (
        db.query(models.TradeLog)
        .filter(models.TradeLog.closing_date.is_(None))
        .filter(models.TradeLog.pnl.is_(None))
        .filter(models.TradeLog.quantity > 0)
        .all()
    )


def _pending_alerts_for_risk(
    risk: TradeRisk,
    trade_key: str,
    cooldown_minutes: float,
    now: float,
) -> list[_PendingAlert]:
    state = _ALERT_STATE.setdefault(trade_key, _TradeAlertMemory())
    alerts: list[_PendingAlert] = []
    stop_alert = _stop_alert_if_needed(risk, trade_key, state, cooldown_minutes, now)
    if stop_alert:
        alerts.append(stop_alert)

    hit_alert = _target_hit_alert_if_needed(risk, trade_key, state, cooldown_minutes, now)
    if hit_alert:
        alerts.append(hit_alert)

    near_alert = _target_near_alert_if_needed(risk, trade_key, state, cooldown_minutes, now)
    if near_alert:
        alerts.append(near_alert)

    return alerts


def _stop_alert_if_needed(
    risk: TradeRisk,
    trade_key: str,
    state: _TradeAlertMemory,
    cooldown_minutes: float,
    now: float,
) -> _PendingAlert | None:
    band = risk.stop_tone
    if band is None:
        state.stop_band = None
        return None

    previous = state.stop_band
    if _STOP_SEVERITY[band] <= _STOP_SEVERITY.get(previous, 0):
        return None

    alert_key = f"{trade_key}:stop:{band}"
    if not _cooldown_allows(state, alert_key, cooldown_minutes, now):
        return None
    return _PendingAlert(
        message=_format_stop_message(risk),
        commit=lambda band=band, alert_key=alert_key: _commit_stop_alert(state, band, alert_key, now),
    )


def _target_hit_alert_if_needed(
    risk: TradeRisk,
    trade_key: str,
    state: _TradeAlertMemory,
    cooldown_minutes: float,
    now: float,
) -> _PendingAlert | None:
    hit_targets = [target for target in risk.target_ladder if target.hit]
    if not hit_targets:
        return None

    hit_labels = {target.label for target in hit_targets}
    new_hit_labels = hit_labels - state.hit_targets
    if not new_hit_labels:
        return None

    target = hit_targets[-1]
    alert_key = f"{trade_key}:target-hit:{target.label}"
    if not _cooldown_allows(state, alert_key, cooldown_minutes, now):
        return None
    return _PendingAlert(
        message=_format_target_hit_message(risk, target),
        commit=lambda hit_labels=hit_labels, alert_key=alert_key: _commit_target_hit_alert(
            state, hit_labels, alert_key, now
        ),
    )


def _target_near_alert_if_needed(
    risk: TradeRisk,
    trade_key: str,
    state: _TradeAlertMemory,
    cooldown_minutes: float,
    now: float,
) -> _PendingAlert | None:
    target = risk.next_target
    if target is None or not _is_target_near(target):
        state.target_near_label = None
        return None

    previous = state.target_near_label
    if previous == target.label:
        return None

    alert_key = f"{trade_key}:target-near:{target.label}"
    if not _cooldown_allows(state, alert_key, cooldown_minutes, now):
        return None
    return _PendingAlert(
        message=_format_target_near_message(risk, target),
        commit=lambda label=target.label, alert_key=alert_key: _commit_target_near_alert(
            state, label, alert_key, now
        ),
    )


def _is_target_near(target: TargetRisk) -> bool:
    has_r = _is_finite(target.r_to_target)
    has_pct = _is_finite(target.pct_to_target)
    if not has_r and not has_pct:
        return False
    if has_r and target.r_to_target is not None and target.r_to_target < 0:
        return False
    if has_pct and target.pct_to_target is not None and target.pct_to_target < 0:
        return False
    return (
        (has_r and target.r_to_target is not None and target.r_to_target <= 0.25)
        or (has_pct and target.pct_to_target is not None and target.pct_to_target <= 1)
    )


def _cooldown_allows(
    state: _TradeAlertMemory,
    alert_key: str,
    cooldown_minutes: float,
    now: float,
) -> bool:
    if cooldown_minutes <= 0:
        return True
    last_fired_at = state.last_fired_at.get(alert_key)
    if last_fired_at is not None and now - last_fired_at < cooldown_minutes * 60:
        return False
    return True


def _commit_stop_alert(state: _TradeAlertMemory, band: str, alert_key: str, now: float) -> None:
    state.stop_band = band
    state.last_fired_at[alert_key] = now


def _commit_target_hit_alert(
    state: _TradeAlertMemory,
    hit_labels: set[str],
    alert_key: str,
    now: float,
) -> None:
    state.hit_targets.update(hit_labels)
    state.last_fired_at[alert_key] = now


def _commit_target_near_alert(
    state: _TradeAlertMemory,
    label: str,
    alert_key: str,
    now: float,
) -> None:
    state.target_near_label = label
    state.last_fired_at[alert_key] = now


def _format_stop_message(risk: TradeRisk) -> str:
    title = f"{risk.ticker} through stop" if risk.stop_tone == "breached" else f"{risk.ticker} near stop"
    return (
        f"Chrollo trade alert: {title} - "
        f"{_fmt_r(risk.r_to_stop)} / {_fmt_pct(risk.dist_to_stop_pct)} to stop "
        f"@ {_fmt_money(risk.current_price)} (stop {_fmt_money(risk.stop_loss)})"
    )


def _format_target_hit_message(risk: TradeRisk, target: TargetRisk) -> str:
    next_detail = "ladder complete"
    if risk.next_target is not None:
        next_detail = (
            f"next {risk.next_target.label} "
            f"{_fmt_r(risk.next_target.r_to_target)} / {_fmt_pct(risk.next_target.pct_to_target)} away"
        )
    return (
        f"Chrollo trade alert: {risk.ticker} hit {target.label} - "
        f"target {_fmt_money(target.price)} reached @ {_fmt_money(risk.current_price)}; {next_detail}"
    )


def _format_target_near_message(risk: TradeRisk, target: TargetRisk) -> str:
    return (
        f"Chrollo trade alert: {risk.ticker} near {target.label} - "
        f"{_fmt_r(target.r_to_target)} / {_fmt_pct(target.pct_to_target)} away "
        f"@ {_fmt_money(risk.current_price)} (target {_fmt_money(target.price)})"
    )


def _cooldown_minutes(value: float | None) -> float:
    if value is not None:
        return float(value)
    settings = load_core_settings()
    return float(getattr(settings, "TRADE_ALERT_COOLDOWN_MINUTES", 0) or 0)


def _prune_closed_trades(open_keys: set[str]) -> None:
    for trade_key in list(_ALERT_STATE):
        if trade_key not in open_keys:
            _ALERT_STATE.pop(trade_key, None)


def _trade_key(trade) -> str:
    return str(getattr(trade, "id", None) or _ticker_for(trade))


def _ticker_for(trade) -> str:
    return str(getattr(trade, "ticker", "") or "").strip().upper()


def _fmt_money(value) -> str:
    if not _is_finite(value):
        return "-"
    return f"${float(value):,.2f}"


def _fmt_pct(value) -> str:
    if not _is_finite(value):
        return "-"
    return f"{float(value):.1f}%"


def _fmt_r(value) -> str:
    if not _is_finite(value):
        return "-"
    return f"{float(value):.2f}R"


def _is_finite(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in {float("inf"), float("-inf")}

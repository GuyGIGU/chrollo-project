"""Market-data cache health, coverage, and repair-state helpers."""
from __future__ import annotations

import hashlib
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import pandas as pd

from config import settings
from core.pipeline.cache import _cache_paths, _read_meta, _write_meta
from core.pipeline.data_freshness import (
    CloseCoverage,
    close_coverage_on,
    deep_history_ratio,
    last_complete_reference_date,
    symbols_missing_closes_on,
    unique_symbols,
)
from core.pipeline.fetch_health import load_quarantine, split_active
from core.pipeline.ticker_admission import load_admission, split_downloadable

REPAIR_STATE_KEY = "repair_state"
PROVIDER_RATE_LIMITED = "provider_rate_limited"
SPARSE_SYMBOLS = "sparse_symbols"
SYMBOL_LAGGING = "symbol_lagging"


@dataclass(frozen=True)
class SymbolScope:
    raw_tickers: list[str]
    raw_symbols: list[str]
    eligible_symbols: list[str]
    eligible_tickers: list[str]
    index_symbols: list[str]
    skipped_admission: list[str]
    skipped_quarantined: list[str]
    admission_skip_counts: dict[str, int]


def build_symbol_scope(tickers: list[str], meta_file: str | None = None,
                       index_symbols: list[str] | None = None) -> SymbolScope:
    if meta_file is None:
        _, meta_file = _cache_paths()
    # ``index_symbols`` is the universe's regime set (callers pass the resolved
    # Universe.index_symbols). Default = the US-Stocks global, so an unparameterized
    # call is byte-identical. An index-less universe (commodities_etf → ()) carries
    # no SPY/QQQ, so it must NOT be forced through them (the universe-blind bug).
    if index_symbols is None:
        index_symbols = list(getattr(settings, "INDEX_SYMBOLS", [settings.SPY_SYMBOL]))
    else:
        index_symbols = list(index_symbols)
    raw_tickers = unique_symbols(list(tickers))
    raw_symbols = unique_symbols(raw_tickers + index_symbols)

    quarantine = (
        load_quarantine(_state_path(meta_file, "QUARANTINE_FILENAME", "ticker_quarantine.json"))
        if getattr(settings, "QUARANTINE_ENABLED", True)
        else {}
    )
    active, skipped_quarantined = split_active(
        raw_symbols, quarantine, index_symbols=index_symbols
    )

    admission = (
        load_admission(_state_path(meta_file, "TICKER_ADMISSION_FILENAME", "ticker_admission.json"))
        if getattr(settings, "TICKER_ADMISSION_ENABLED", True)
        else {}
    )
    eligible_symbols, skipped_admission, admission_skip_counts = split_downloadable(
        active, admission, index_symbols=index_symbols
    )
    eligible_tickers = [s for s in eligible_symbols if s not in set(index_symbols)]
    return SymbolScope(
        raw_tickers=raw_tickers,
        raw_symbols=raw_symbols,
        eligible_symbols=eligible_symbols,
        eligible_tickers=eligible_tickers,
        index_symbols=index_symbols,
        skipped_admission=skipped_admission,
        skipped_quarantined=skipped_quarantined,
        admission_skip_counts=admission_skip_counts,
    )


def eligible_tickers_for(tickers: list[str], meta_file: str | None = None,
                         index_symbols: list[str] | None = None) -> list[str]:
    return build_symbol_scope(tickers, meta_file, index_symbols).eligible_tickers


def compute_market_data_health(
    data: pd.DataFrame,
    tickers: list[str],
    *,
    expected_session: pd.Timestamp | None = None,
    meta: dict | None = None,
    meta_file: str | None = None,
    index_symbols: list[str] | None = None,
    now_utc: datetime | None = None,
    closed_reason: str | None = None,
    weekly_refresh_due: bool = False,
) -> dict:
    if meta_file is None:
        _, meta_file = _cache_paths()
    if meta is None:
        meta = _read_meta(meta_file)
    if expected_session is None:
        from core.pipeline.market_calendar import latest_completed_session
        expected_session = latest_completed_session()
    expected_session = pd.Timestamp(expected_session).normalize()
    now_utc = _as_utc(now_utc)

    panel = _normalize_index(data)
    scope = build_symbol_scope(tickers, meta_file, index_symbols)
    min_coverage = float(getattr(settings, "MARKET_DATA_MIN_LATEST_COVERAGE", 0.95))

    raw_coverage = close_coverage_on(panel, scope.raw_symbols, expected_session)
    eligible_coverage = close_coverage_on(panel, scope.eligible_symbols, expected_session)
    raw_missing = symbols_missing_closes_on(panel, scope.raw_symbols, expected_session)
    eligible_missing = symbols_missing_closes_on(panel, scope.eligible_symbols, expected_session)
    index_missing = symbols_missing_closes_on(panel, scope.index_symbols, expected_session)
    last_reference = last_complete_reference_date(panel, scope.index_symbols)
    cache_last_session = last_reference
    if cache_last_session is None and panel is not None and not panel.empty:
        cache_last_session = pd.Timestamp(panel.index.max()).normalize()
    if not scope.index_symbols:
        # Index-less universe (e.g. commodities_etf): there is no SPY/QQQ reference
        # bar to anchor on, so freshness is judged purely on the panel's own latest
        # session + eligible coverage. Without this, last_reference is always None
        # and _classify reads the universe as stale_session on EVERY run, making it
        # permanently un-evaluable and un-archivable.
        last_reference = cache_last_session

    repair_state = repair_state_from_meta(meta, now_utc)
    missing_summary = _missing_summary(
        panel, scope, raw_missing, eligible_missing, expected_session
    )
    # Deep-history integrity (the "second half" of the multi-universe cache bug).
    # Only judged when the panel itself spans >= the bar floor — a short/new cache
    # can't carry deep symbols and must NOT be flagged. Below the coverage floor =>
    # the NaN-wipe shape (recent bars, hollow history) => not trustworthy for
    # archive/eval; refresh / fetch_data force a full cold refetch instead.
    min_history_bars = int(getattr(settings, "MARKET_DATA_MIN_HISTORY_BARS", 100))
    min_history_cov = float(getattr(settings, "MARKET_DATA_MIN_HISTORY_COVERAGE", 0.5))
    history_ok = True
    if (scope.eligible_symbols and panel is not None and not panel.empty
            and len(panel.index) >= min_history_bars):
        history_ok = deep_history_ratio(
            panel, scope.eligible_symbols, min_history_bars
        ) >= min_history_cov
    health_state, severity, can_evaluate, can_archive, can_download, help_needed = _classify(
        cache_last_session,
        last_reference,
        expected_session,
        index_missing,
        eligible_coverage,
        min_coverage,
        repair_state,
        closed_reason,
        weekly_refresh_due,
        history_ok,
    )

    diagnosis = _diagnosis(
        health_state,
        raw_coverage,
        eligible_coverage,
        min_coverage,
        missing_summary,
        cache_last_session,
        expected_session,
        repair_state,
    )
    download_label = _download_label(
        health_state,
        can_download,
        weekly_refresh_due,
        missing_summary["eligible_missing_count"],
        repair_state,
    )

    coverage = {
        "raw": _coverage_payload(raw_coverage),
        "eligible": _coverage_payload(eligible_coverage),
        "archive_target": min_coverage,
        # Compatibility: previous callers expected coverage.text/ratio.
        **_coverage_payload(eligible_coverage),
    }
    return {
        "health_state": health_state,
        "status": health_state,
        "severity": severity,
        "can_evaluate": can_evaluate,
        "can_archive": can_archive,
        "can_download": can_download,
        "download_label": download_label,
        "message": diagnosis,
        "diagnosis": diagnosis,
        "help_needed": help_needed,
        "expected_session": _date_str(expected_session),
        "cache_last_session": _date_str(cache_last_session),
        "coverage": coverage,
        "missing_summary": missing_summary,
        "next_retry_at": repair_state.get("next_retry_at"),
        "retry_seconds": repair_state.get("retry_seconds", 0),
        "retry_reason": repair_state.get("retry_reason"),
        "repair_state": repair_state,
    }


def record_repair_attempt(
    meta_file: str,
    before_health: dict | None,
    after_health: dict | None,
    *,
    error_text: str | None = None,
    now_utc: datetime | None = None,
) -> dict:
    now_utc = _as_utc(now_utc)
    meta = _read_meta(meta_file)
    previous = meta.get(REPAIR_STATE_KEY) if isinstance(meta.get(REPAIR_STATE_KEY), dict) else {}
    after_missing = _eligible_missing(after_health)
    before_missing = _eligible_missing(before_health)
    signature = missing_signature(after_missing or before_missing)
    previous_same = previous.get("missing_signature") == signature
    attempt_count = int(previous.get("attempt_count", 0)) + 1 if previous_same else 1

    error_class = classify_provider_error(error_text) if error_text else None
    retry_seconds = None
    help_needed = False
    if error_class == PROVIDER_RATE_LIMITED:
        retry_seconds = parse_retry_after_seconds(error_text, now_utc)
        if retry_seconds is None:
            retry_seconds = 20 * 60 if attempt_count > 1 else 15 * 60
        help_needed = attempt_count >= 2
    elif after_health and not after_health.get("can_archive", False):
        if attempt_count == 1:
            retry_seconds = int(getattr(settings, "MARKET_DATA_REPAIR_FIRST_RETRY_MINUTES", 10)) * 60
            error_class = SPARSE_SYMBOLS
        elif attempt_count == 2:
            retry_seconds = int(getattr(settings, "MARKET_DATA_REPAIR_SECOND_RETRY_MINUTES", 20)) * 60
            error_class = SPARSE_SYMBOLS
        else:
            error_class = SYMBOL_LAGGING
            help_needed = True
    else:
        clear_repair_state(meta_file)
        return {}

    next_retry_at = (
        (now_utc + timedelta(seconds=max(0, int(retry_seconds)))).isoformat()
        if retry_seconds is not None
        else None
    )
    state = {
        "last_attempt_at": now_utc.isoformat(),
        "attempt_count": attempt_count,
        "missing_signature": signature,
        "missing_eligible_before": len(before_missing),
        "missing_eligible_after": len(after_missing),
        "returned_count": max(0, len(before_missing) - len(after_missing)),
        "error_class": error_class or SPARSE_SYMBOLS,
        "next_retry_at": next_retry_at,
        "retry_reason": _retry_reason(error_class or SPARSE_SYMBOLS, len(after_missing)),
        "help_needed": help_needed,
    }
    if after_health:
        state["eligible_coverage_after"] = after_health["coverage"]["eligible"]["ratio"]
        state["raw_coverage_after"] = after_health["coverage"]["raw"]["ratio"]
    meta[REPAIR_STATE_KEY] = state
    meta.pop("repair_cooldown_until", None)
    meta.pop("repair_cooldown_reason", None)
    _write_meta(meta_file, meta)
    return repair_state_from_meta(meta, now_utc)


def clear_repair_state(meta_file: str) -> None:
    meta = _read_meta(meta_file)
    changed = False
    for key in (REPAIR_STATE_KEY, "repair_cooldown_until", "repair_cooldown_reason"):
        if key in meta:
            meta.pop(key, None)
            changed = True
    if changed:
        _write_meta(meta_file, meta)


def repair_state_from_meta(meta: dict, now_utc: datetime | None = None) -> dict:
    now_utc = _as_utc(now_utc)
    state = meta.get(REPAIR_STATE_KEY) if isinstance(meta.get(REPAIR_STATE_KEY), dict) else {}
    if not state and meta.get("repair_cooldown_until"):
        state = {
            "next_retry_at": meta.get("repair_cooldown_until"),
            "retry_reason": meta.get("repair_cooldown_reason"),
            "error_class": SPARSE_SYMBOLS,
            "attempt_count": 1,
        }
    next_retry_at = state.get("next_retry_at")
    retry_seconds = _seconds_until(next_retry_at, now_utc)
    out = dict(state)
    out["active"] = retry_seconds > 0
    out["retry_seconds"] = retry_seconds
    out["help_needed"] = bool(out.get("help_needed"))
    return out


def classify_provider_error(text: str | None) -> str | None:
    text = (text or "").lower()
    if "429" in text or "too many requests" in text or "yfratelimiterror" in text:
        return PROVIDER_RATE_LIMITED
    return None


def parse_retry_after_seconds(text: str | None, now_utc: datetime | None = None) -> int | None:
    if not text:
        return None
    now_utc = _as_utc(now_utc)
    match = re.search(r"retry-after\s*[:=]\s*([^\r\n;,]+)", text, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip().strip("'\"")
    if value.isdigit():
        return max(0, int(value))
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    retry_at = _as_utc(retry_at)
    return max(0, int((retry_at - now_utc).total_seconds()))


def missing_signature(symbols: list[str]) -> str:
    payload = "\n".join(sorted(unique_symbols(symbols)))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def _classify(cache_last_session, last_reference, expected_session, index_missing,
              eligible_coverage, min_coverage, repair_state, closed_reason,
              weekly_refresh_due, history_ok=True):
    if last_reference is None or index_missing or cache_last_session is None:
        return "stale_session", "blocked", False, False, True, True
    if pd.Timestamp(last_reference).normalize() < expected_session:
        return "stale_session", "blocked", False, False, True, True
    if eligible_coverage.ratio >= min_coverage:
        if not history_ok:
            # Latest session is current but most symbols lost their multi-year
            # history (the NaN-wipe shape). Refuse to trust it for archive/eval and
            # force a full cold refetch — never a latest-session-only repair, which
            # would leave the deep history hollow.
            return "shallow_history", "repair", False, False, True, True
        if weekly_refresh_due:
            return "healthy", "watch", True, True, True, False
        if closed_reason in {"weekend", "holiday", "before_open"}:
            return "market_wait", "ok", True, True, False, False
        return "healthy", "ok", True, True, False, False

    error_class = repair_state.get("error_class")
    if error_class == PROVIDER_RATE_LIMITED and repair_state.get("active"):
        return "provider_cooldown", "blocked", False, False, False, repair_state.get("help_needed", False)
    if error_class == SYMBOL_LAGGING:
        return "symbol_lagging", "blocked", False, False, False, True
    if repair_state.get("active"):
        return "needs_repair", "watch", False, False, False, False
    return "needs_repair", "repair", False, False, True, False


def _diagnosis(health_state, raw_coverage, eligible_coverage, min_coverage,
               missing_summary, cache_last_session, expected_session, repair_state):
    raw_text = raw_coverage.format()
    eligible_text = eligible_coverage.format()
    skipped = missing_summary["skipped_missing_count"]
    eligible_missing = missing_summary["eligible_missing_count"]
    base = f"Eligible coverage {eligible_text}; raw coverage {raw_text}."
    if skipped:
        base += f" {skipped} missing raw symbol(s) are admission/quarantine-skipped."
    if eligible_missing:
        base += f" {eligible_missing} eligible symbol(s) still lag the latest session."
    if health_state == "healthy":
        return f"{base} Archive target {min_coverage:.0%} is met."
    if health_state == "market_wait":
        return f"{base} Market is closed or waiting for the next completed session."
    if health_state == "stale_session":
        return (
            f"Cache reference session is {cache_last_session.date() if cache_last_session is not None else 'missing'}; "
            f"expected {expected_session.date()}."
        )
    if health_state == "shallow_history":
        return (
            f"{base} Cache is current but most symbols are missing their deep "
            f"history (truncated cache); a full cold refetch is required."
        )
    if health_state == "provider_cooldown":
        return f"{base} Provider retry is cooling down: {repair_state.get('retry_reason') or 'rate limited'}."
    if health_state == "symbol_lagging":
        return f"{base} The same symbols stayed stale after bounded repairs; review or wait for the next session."
    return f"{base} Repair eligible missing symbols before archive-quality evaluation."


def _download_label(health_state, can_download, weekly_refresh_due, eligible_missing, repair_state):
    if health_state == "healthy" and weekly_refresh_due:
        return "Refresh Data"
    if health_state in {"healthy", "market_wait"}:
        return "Not needed"
    if repair_state.get("active") and not can_download:
        return f"Cooldown {_minutes_label(repair_state.get('retry_seconds', 0))}"
    if health_state == "symbol_lagging":
        return "Needs help"
    if health_state == "provider_cooldown":
        return "Provider limited"
    if health_state == "stale_session":
        return "Download New Data"
    if health_state == "shallow_history":
        return "Rebuild Data"
    if health_state == "needs_repair":
        return f"Repair {eligible_missing}" if eligible_missing else "Repair Data"
    return "Download New Data"


def _missing_summary(panel, scope: SymbolScope, raw_missing: list[str],
                     eligible_missing: list[str], expected_session: pd.Timestamp) -> dict:
    skipped = set(scope.skipped_admission) | set(scope.skipped_quarantined)
    skipped_missing = [s for s in raw_missing if s in skipped]
    latest_dates, bar_counts = _latest_close_facts(panel, scope.raw_symbols)
    latest_counts = Counter(latest_dates.get(s, "NO_HISTORY") for s in eligible_missing)
    skipped_status_counts = Counter()
    for status, count in scope.admission_skip_counts.items():
        skipped_status_counts[status] += count
    if scope.skipped_quarantined:
        skipped_status_counts["quarantined"] += len(scope.skipped_quarantined)
    zero_history = [s for s in eligible_missing if bar_counts.get(s, 0) == 0]
    active_stale = [s for s in eligible_missing if bar_counts.get(s, 0) > 0]
    samples = [
        {
            "ticker": symbol,
            "latest": latest_dates.get(symbol),
            "bars": bar_counts.get(symbol, 0),
        }
        for symbol in eligible_missing[:12]
    ]
    return {
        "raw_missing_count": len(raw_missing),
        "eligible_missing_count": len(eligible_missing),
        "skipped_missing_count": len(skipped_missing),
        "skipped_admission_count": len(scope.skipped_admission),
        "skipped_quarantined_count": len(scope.skipped_quarantined),
        "skip_counts": dict(skipped_status_counts),
        "zero_history_count": len(zero_history),
        "active_ready_stale_count": len(active_stale),
        "latest_date_lag": dict(latest_counts),
        "eligible_missing_symbols": eligible_missing,
        "sample_tickers": samples,
        "expected_session": _date_str(expected_session),
    }


def _latest_close_facts(panel: pd.DataFrame, symbols: list[str]) -> tuple[dict[str, str], dict[str, int]]:
    if panel is None or panel.empty or not isinstance(panel.columns, pd.MultiIndex):
        return {}, {}
    try:
        closes = panel.xs("Close", axis=1, level=1)
    except KeyError:
        return {}, {}
    latest: dict[str, str] = {}
    counts: dict[str, int] = {}
    for symbol in symbols:
        if symbol not in closes.columns:
            counts[symbol] = 0
            continue
        series = closes[symbol].dropna()
        counts[symbol] = int(len(series))
        if not series.empty:
            latest[symbol] = pd.Timestamp(series.index.max()).date().isoformat()
    return latest, counts


def _coverage_payload(coverage: CloseCoverage) -> dict:
    return {
        "day": _date_str(coverage.day),
        "present": coverage.present,
        "total": coverage.total,
        "ratio": coverage.ratio,
        "text": coverage.format(),
    }


def _eligible_missing(health: dict | None) -> list[str]:
    if not health:
        return []
    summary = health.get("missing_summary") or {}
    return list(summary.get("eligible_missing_symbols") or [])


def _retry_reason(error_class: str, missing_count: int) -> str:
    if error_class == PROVIDER_RATE_LIMITED:
        return "provider rate limit"
    if error_class == SYMBOL_LAGGING:
        return f"{missing_count} symbol(s) stayed stale after bounded repairs"
    return f"{missing_count} symbol(s) still missing the latest close"


def _state_path(meta_file: str, setting_name: str, default_name: str) -> str:
    return os.path.join(os.path.dirname(meta_file), getattr(settings, setting_name, default_name))


def _normalize_index(data: pd.DataFrame) -> pd.DataFrame:
    if hasattr(data.index, "tz") and data.index.tz is not None:
        data = data.copy()
        data.index = data.index.tz_localize(None)
    return data


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _seconds_until(value, now_utc: datetime) -> int:
    if not value:
        return 0
    try:
        when = datetime.fromisoformat(str(value))
    except ValueError:
        return 0
    when = _as_utc(when)
    return max(0, int((when - now_utc).total_seconds()))


def _minutes_label(seconds: int) -> str:
    return f"{max(1, int((int(seconds) + 59) // 60))}m"


def _date_str(value) -> str | None:
    if value is None:
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")

"""Ticker admission ledger for avoiding wasted Yahoo history downloads.

The directory filter handles deterministic non-stock instruments up front. The
ledger then remembers history-readiness from real fetch results so too-young or
empty symbols are skipped until their next recheck window.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import settings
from core.pipeline.market_data.cache import atomic_write_json

STATUS_READY = "active_ready"
STATUS_YOUNG = "active_young"
STATUS_EMPTY = "yahoo_empty"
STATUS_INVALID = "invalid_instrument"
STATUS_ANOMALY = "provider_anomaly"

_SPECIAL_ISSUE_SUFFIXES = {"R", "U", "W"}  # rights, units, warrants


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_aware(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def load_admission(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_admission(path: str, store: dict) -> None:
    # The shared atomic-JSON primitive (EC-3), NOT a hand-rolled copy of it: the
    # ledger is shared by all three universes, two writers sharing one fixed
    # '.tmp' can tear the JSON (load then fails open to {}, silently resetting
    # admission state), and this write sits between the parquet write and the
    # meta write, so a bare os.replace losing the Windows PermissionError retry
    # aborts a cold run with the cache and its metadata already disagreeing.
    atomic_write_json(path, store, sort_keys=True)


def _entry(status: str, reason: str, *, now=None, next_check=None, **extra) -> dict:
    now = now or _now()
    row = {
        "status": status,
        "reason": reason,
        "last_checked": now.isoformat(),
    }
    if next_check is not None:
        row["next_check"] = next_check.isoformat()
    row.update(extra)
    return row


def _reject_reason_from_name(security_name: str) -> str | None:
    name = (security_name or "").upper()
    if "WARRANT" in name:
        return "warrant"
    if (" RIGHTS" in name or " RIGHT" in name) and "RIGHT TO RECEIVE" not in name:
        return "rights"
    if " - UNITS" in name or " - UNIT" in name or name.endswith(" - UNITS"):
        return "unit"
    if "PREFERRED" in name or "PREFERENCE SHARE" in name or "PREFERENCE STOCK" in name:
        return "preferred"
    if "SENIOR NOTES" in name or "SUBORDINATED NOTES" in name or "NOTES DUE" in name:
        return "notes"
    if "DEBENTURE" in name or "DEBENTURES" in name:
        return "debenture"
    if " ETN" in name or name.endswith(" ETN"):
        return "etn"
    if "CLOSED END FUND" in name:
        return "closed_end_fund"
    return None


def _symbol_reject_reason(symbol: str) -> str | None:
    if not symbol or not symbol.isalpha() or len(symbol) > 5:
        return "invalid_symbol"
    if len(symbol) == 5 and symbol[-1] in _SPECIAL_ISSUE_SUFFIXES:
        return "special_issue_suffix"
    return None


def screen_symbols(raw_tickers, skiplist: set[str] | None = None) -> tuple[list[str], dict[str, int]]:
    """Filter cached symbol-only CSV rows. Preserves order while deduping."""
    skiplist = skiplist or set()
    tickers: list[str] = []
    seen: set[str] = set()
    stats = Counter()

    for raw in raw_tickers:
        if pd.isna(raw):
            continue
        symbol = str(raw).strip().upper()
        reject_reason = _symbol_reject_reason(symbol)
        if reject_reason == "special_issue_suffix":
            stats["special_issue"] += 1
            continue
        if reject_reason:
            stats["invalid"] += 1
            continue
        if symbol in skiplist:
            stats["manual_skip"] += 1
            continue
        if symbol in seen:
            stats["duplicate"] += 1
            continue
        tickers.append(symbol)
        seen.add(symbol)

    return tickers, dict(stats)


def screen_directory_rows(df_table: pd.DataFrame, skiplist: set[str] | None = None):
    """Filter a NASDAQ Trader directory table using symbol + security name facts.

    Returns ``(tickers, stats, rejected_entries)``. ``rejected_entries`` can be
    persisted to the admission ledger as permanent invalid-instrument skips.
    """
    skiplist = skiplist or set()
    tickers: list[str] = []
    seen: set[str] = set()
    rejected: dict[str, dict] = {}
    stats = Counter()

    target_col = next(
        (col for col in df_table.columns if col.lower() in ["symbol", "ticker symbol", "ticker"]),
        None,
    )
    if not target_col:
        return tickers, {"invalid": 0}, rejected

    for _, row in df_table.iterrows():
        raw = row.get(target_col)
        if pd.isna(raw):
            continue
        symbol = str(raw).strip().upper()
        security_name = str(row.get("Security Name") or "")
        reject_reason = _symbol_reject_reason(symbol)
        if reject_reason == "special_issue_suffix":
            stats["special_issue"] += 1
            rejected[symbol] = {
                "status": STATUS_INVALID,
                "reason": reject_reason,
                "security_name": security_name,
            }
            continue
        if reject_reason:
            stats["invalid"] += 1
            continue
        if symbol in skiplist:
            stats["manual_skip"] += 1
            continue
        name_reason = _reject_reason_from_name(security_name)
        if name_reason:
            stats["invalid_instrument"] += 1
            rejected[symbol] = {
                "status": STATUS_INVALID,
                "reason": name_reason,
                "security_name": security_name,
            }
            continue
        if symbol in seen:
            stats["duplicate"] += 1
            continue
        tickers.append(symbol)
        seen.add(symbol)

    return tickers, dict(stats), rejected


def record_directory_rejections(store: dict, rejected: dict[str, dict], *, now=None) -> dict:
    now = now or _now()
    for symbol, info in rejected.items():
        store[symbol] = _entry(
            STATUS_INVALID,
            info.get("reason") or "directory_filter",
            now=now,
            security_name=info.get("security_name"),
        )
    return store


def split_downloadable(tickers, store, *, now=None, index_symbols=None):
    """Partition symbols into downloadable vs. admission-skipped."""
    now = now or _now()
    index_symbols = set(index_symbols or [])
    active: list[str] = []
    skipped: list[str] = []
    counts = Counter()

    for ticker in tickers:
        if ticker in index_symbols:
            active.append(ticker)
            continue
        entry = store.get(ticker)
        status = entry.get("status") if isinstance(entry, dict) else None
        if status == STATUS_INVALID:
            skipped.append(ticker)
            counts[status] += 1
            continue
        if status in {STATUS_YOUNG, STATUS_EMPTY, STATUS_ANOMALY}:
            next_check = _parse_iso_aware(entry.get("next_check"))
            if next_check is not None and now < next_check:
                skipped.append(ticker)
                counts[status] += 1
                continue
        active.append(ticker)

    return active, skipped, dict(counts)


def close_counts(panel) -> dict[str, int]:
    if panel is None or getattr(panel, "empty", True) or not isinstance(panel.columns, pd.MultiIndex):
        return {}
    try:
        closes = panel.xs("Close", axis=1, level=1)
    except KeyError:
        return {}
    return closes.notna().sum().astype(int).to_dict()


def latest_close_dates(panel) -> dict[str, str]:
    if panel is None or getattr(panel, "empty", True) or not isinstance(panel.columns, pd.MultiIndex):
        return {}
    try:
        closes = panel.xs("Close", axis=1, level=1)
    except KeyError:
        return {}
    latest: dict[str, str] = {}
    for ticker in closes.columns:
        series = closes[ticker].dropna()
        if not series.empty:
            latest[ticker] = series.index.max().date().isoformat()
    return latest


def record_history_results(store: dict, requested, panel, *, now=None,
                           mark_missing: bool = True) -> tuple[dict, dict[str, int]]:
    """Update admission from a history panel after a healthy fetch."""
    now = now or _now()
    min_bars = int(getattr(settings, "ADMISSION_MIN_HISTORY_BARS", 200))
    young_days = int(getattr(settings, "ADMISSION_YOUNG_RECHECK_DAYS", 21))
    empty_days = int(getattr(settings, "ADMISSION_EMPTY_RECHECK_DAYS", 7))
    counts = close_counts(panel)
    latest = latest_close_dates(panel)
    summary = Counter()

    for ticker in requested:
        bars = int(counts.get(ticker, 0))
        if bars >= min_bars:
            store[ticker] = _entry(
                STATUS_READY,
                "history_ready",
                now=now,
                bars=bars,
                latest_close=latest.get(ticker),
            )
            summary[STATUS_READY] += 1
        elif bars > 0:
            store[ticker] = _entry(
                STATUS_YOUNG,
                "history_bars_below_min",
                now=now,
                next_check=now + timedelta(days=young_days),
                bars=bars,
                latest_close=latest.get(ticker),
                min_bars=min_bars,
            )
            summary[STATUS_YOUNG] += 1
        else:
            if not mark_missing:
                continue
            previous = store.get(ticker) if isinstance(store.get(ticker), dict) else {}
            empty_streak = int(previous.get("empty_streak", 0)) + 1
            store[ticker] = _entry(
                STATUS_EMPTY,
                "no_history_returned",
                now=now,
                next_check=now + timedelta(days=empty_days),
                bars=0,
                empty_streak=empty_streak,
            )
            summary[STATUS_EMPTY] += 1

    return store, dict(summary)


def count_active_skips(store: dict, *, now=None) -> dict[str, int]:
    now = now or _now()
    counts = Counter()
    for entry in store.values():
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        if status == STATUS_INVALID:
            counts[status] += 1
        elif status in {STATUS_YOUNG, STATUS_EMPTY, STATUS_ANOMALY}:
            next_check = _parse_iso_aware(entry.get("next_check"))
            if next_check is not None and now < next_check:
                counts[status] += 1
    return dict(counts)

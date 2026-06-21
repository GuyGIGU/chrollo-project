"""Dead-ticker quarantine + per-run fetch-health telemetry for the Yahoo data path.

The screener's universe (~6.9k NASDAQ-traded symbols) carries a long tail of
delisted / halted / invalid tickers that return nothing from Yahoo on every run.
Re-requesting them daily wastes request budget, drives 429s, and triggers the
per-ticker recovery storm in ``downloads._recover_missing_data``. This module
skips symbols that repeatedly come back empty — re-probing them after a cooldown
so a re-listing recovers — and records a small per-run health summary so fetch
quality is observable and tunable instead of guessed.

Design (integrated by ``downloads.fetch_data``):
- FILTER the universe up front every run (cheap; skips quarantined symbols).
- RECORD results only on the cold full-refetch — the strongest death signal,
  since every absent ticker there already got a dedicated per-ticker retry. The
  incremental path never updates quarantine (a ticker absent from a small
  incremental window is not necessarily dead; it lives in the cache).
- GATE recording on a healthy run: if too few of the requested symbols returned
  (a rate-limited day), skip the streak update so a bad Yahoo day can't
  quarantine the whole universe.

Pure transforms + small JSON IO; no network, no yfinance, no module-level
``settings`` reads (lazy ``getattr`` only), per the config-shadowing constraint.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pandas as pd

from config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso_aware(value) -> datetime | None:
    """Parse an ISO timestamp to an aware (UTC-coerced) datetime, or None."""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


# ------------------------------------------------------------------
# Quarantine store IO (small JSON beside the cache meta)
# ------------------------------------------------------------------
def load_quarantine(path: str) -> dict:
    """Read the quarantine store; return {} if absent or unreadable (fail-open)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_quarantine(path: str, store: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


# ------------------------------------------------------------------
# Pure transforms
# ------------------------------------------------------------------
def split_active(tickers, store, *, now=None, cooldown_days=None, index_symbols=None):
    """Partition ``tickers`` into ``(active, skipped)``.

    A ticker is skipped iff it is quarantined and still inside its cooldown
    window. Index symbols are never skipped.
    """
    now = now or _now()
    if cooldown_days is None:
        cooldown_days = getattr(settings, "QUARANTINE_COOLDOWN_DAYS", 7)
    index_symbols = set(index_symbols or [])
    active: list[str] = []
    skipped: list[str] = []
    for ticker in tickers:
        if ticker in index_symbols:
            active.append(ticker)
            continue
        entry = store.get(ticker)
        until = _parse_iso_aware(entry.get("quarantined_until")) if isinstance(entry, dict) else None
        if until is not None and now < until:
            skipped.append(ticker)
        else:
            active.append(ticker)
    return active, skipped


def present_tickers(panel) -> set:
    """Tickers in a ``(ticker, field)`` panel carrying at least one non-NaN Close.

    Vectorized (one ``notna().any()`` over all Close columns) — it runs over the
    whole ~6.9k-symbol panel on every incremental write, so the per-ticker Python
    loop is avoided.
    """
    if panel is None or getattr(panel, "empty", True):
        return set()
    if not isinstance(panel.columns, pd.MultiIndex):
        return set()
    try:
        closes = panel.xs("Close", axis=1, level=1)
    except KeyError:
        return set()
    any_close = closes.notna().any()
    return set(any_close.index[any_close])


def record_results(store, requested, returned, *, now=None,
                   streak_threshold=None, cooldown_days=None):
    """Update the quarantine store after a healthy fetch.

    Returned tickers are rehabilitated (dropped from the store). Requested-but-
    absent tickers accrue an empty streak; on reaching the threshold they are
    quarantined for the cooldown window (re-quarantining extends it). Returns
    ``(store, newly_quarantined)``. Mutates ``store`` in place.
    """
    now = now or _now()
    if streak_threshold is None:
        streak_threshold = getattr(settings, "QUARANTINE_EMPTY_STREAK", 2)
    if cooldown_days is None:
        cooldown_days = getattr(settings, "QUARANTINE_COOLDOWN_DAYS", 7)
    now_iso = now.isoformat()
    until_iso = (now + timedelta(days=cooldown_days)).isoformat()
    returned = set(returned)
    newly: list[str] = []
    for ticker in requested:
        if ticker in returned:
            store.pop(ticker, None)
            continue
        entry = store.get(ticker) or {"empty_streak": 0, "first_empty": now_iso}
        entry["empty_streak"] = int(entry.get("empty_streak", 0)) + 1
        entry["last_empty"] = now_iso
        if entry["empty_streak"] >= streak_threshold:
            if not entry.get("quarantined_until"):
                newly.append(ticker)
            entry["quarantined_until"] = until_iso
        store[ticker] = entry
    return store, newly


def count_quarantined(store, now=None) -> int:
    """Number of tickers currently inside an active cooldown window."""
    now = now or _now()
    total = 0
    for entry in store.values():
        if not isinstance(entry, dict):
            continue
        until = _parse_iso_aware(entry.get("quarantined_until"))
        if until is not None and now < until:
            total += 1
    return total


def _ratio(requested, returned) -> tuple[int, int, float]:
    n_req = requested if isinstance(requested, int) else len(requested)
    n_ret = returned if isinstance(returned, int) else len(returned)
    return n_req, n_ret, (n_ret / n_req) if n_req else 0.0


def is_healthy(requested, returned, min_healthy_ratio=None) -> bool:
    if min_healthy_ratio is None:
        min_healthy_ratio = getattr(settings, "QUARANTINE_MIN_HEALTHY_RATIO", 0.5)
    n_req, _, ratio = _ratio(requested, returned)
    return bool(n_req) and ratio >= min_healthy_ratio


def summarize(mode, requested, returned, skipped_quarantined, newly_quarantined,
              quarantined_total, duration_s, *, now=None, min_healthy_ratio=None):
    """Build the per-run fetch-health record stashed in ``cache_meta.json``."""
    now = now or _now()
    if min_healthy_ratio is None:
        min_healthy_ratio = getattr(settings, "QUARANTINE_MIN_HEALTHY_RATIO", 0.5)
    n_req, n_ret, ratio = _ratio(requested, returned)
    return {
        "ts": now.isoformat(),
        "mode": mode,
        "requested": n_req,
        "returned": n_ret,
        "return_ratio": round(ratio, 4),
        "skipped_quarantined": int(skipped_quarantined),
        "newly_quarantined": int(newly_quarantined),
        "quarantined_total": int(quarantined_total),
        "duration_s": round(float(duration_s), 1),
        "healthy": ratio >= min_healthy_ratio,
    }

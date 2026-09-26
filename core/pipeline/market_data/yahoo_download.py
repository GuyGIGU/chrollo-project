"""Yahoo price-history requests, shared by the cache and the archive downloads.

One request (``_download_batch_with_retry``) with retry and backoff, and the bounded
pool (``_batched_download``) that fans a ticker list out over it. Every request passes
the shared token bucket, and a Yahoo 429 arms the shared cooldown so every worker
waits it out, not only the one that was refused (``rate_limit``).
"""
from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf

from config import settings
from core.pipeline.market_data import rate_limit
from core.pipeline.market_data.price_regime import price_auto_adjust


def _is_yahoo_rate_limit_text(text: str) -> bool:
    text = str(text).lower()
    return (
        "yfratelimiterror" in text
        or "too many requests" in text
        or "rate limited" in text
    )


def _is_yahoo_rate_limit_error(exc: Exception) -> bool:
    return _is_yahoo_rate_limit_text(f"{type(exc).__name__}: {exc}")


def _is_yahoo_no_history_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return (
        "yftzmissingerror" in text
        or "possibly delisted" in text
        or "no price data found" in text
        or "no timezone found" in text
    )


def _rate_limit_backoff_seconds() -> float:
    return float(getattr(settings, "YAHOO_RATE_LIMIT_BACKOFF_SECONDS", 30.0))


def _apply_backoff_jitter(wait: float) -> float:
    """Randomize the lower part of a backoff so many workers that got rate-limited
    at once don't retry in a synchronized burst (which just re-trips Yahoo). Keeps
    ``(1 - jitter)`` of the wait fixed and randomizes the rest, so the result is in
    ``[wait*(1-jitter), wait]``. The *base* backoff (``2**attempt``) still grows across
    retries; the jitter only spreads each attempt's wait within its own band, so a lucky
    low draw on a later attempt can dip below an earlier one — intended (it de-syncs the
    workers; the shared cooldown still enforces the real floor)."""
    jitter = min(max(float(getattr(settings, "YAHOO_BACKOFF_JITTER", 0.5)), 0.0), 1.0)
    if jitter <= 0.0:
        return wait
    return wait * (1.0 - jitter) + random.uniform(0.0, wait * jitter)


def _retry_wait_seconds(attempt: int, exc: Exception | None = None, error_text: str = "") -> float:
    wait = float(2 ** attempt)
    if ((exc is not None and _is_yahoo_rate_limit_error(exc))
            or (error_text and _is_yahoo_rate_limit_text(error_text))):
        wait = max(wait, _rate_limit_backoff_seconds())
        # Invariant: the shared cooldown gets the FULL un-jittered wait; the per-worker retry
        # sleep (the jittered return below) is shorter and may end BEFORE the shared window does.
        # That is fine — rate_limit._respect_cooldown() is the authoritative gate that re-parks a
        # worker whose local sleep ended early. Do NOT drop that second cooldown check thinking the
        # local sleep already covered it, or lockstep bursts come back.
        rate_limit.note_rate_limit(wait)
    return _apply_backoff_jitter(wait)


def _last_yahoo_batch_error_text(batch: list[str]) -> str:
    """Return yfinance's latest batch errors after a sequential yf.download call."""
    try:
        from yfinance import shared as yf_shared
        errors = getattr(yf_shared, "_ERRORS", {}) or {}
    except Exception:
        return ""
    parts = [str(errors.get(ticker.upper(), "")) for ticker in batch]
    return " | ".join(part for part in parts if part)


def _drop_index_tz(frame: pd.DataFrame) -> pd.DataFrame:
    """Make ``frame``'s index tz-naive, in place, and return it. Yahoo's history
    index is tz-aware; every panel the cache holds is tz-naive."""
    if hasattr(frame.index, 'tz') and frame.index.tz is not None:
        frame.index = frame.index.tz_localize(None)
    return frame


def _drop_adj_close(data: pd.DataFrame) -> pd.DataFrame:
    """Strip yfinance's extra 'Adj Close' field — the cache schema (and every
    downstream reader) is strictly OHLCV.

    Needed on BOTH download shapes when auto_adjust=False: the pinned yfinance
    1.2.1 emits 'Adj Close' from ``Ticker().history`` too (even with
    ``actions=False``), and every production download goes through the
    single-ticker path. An asymmetric drop would also poison repair patches:
    frames with mismatched field sets combine into NaN-striped rows that
    ``dropna`` then silently eats."""
    if (data is not None and not data.empty
            and isinstance(data.columns, pd.MultiIndex)):
        return data.drop(columns="Adj Close", level=1, errors="ignore")
    return data


def _single_ticker_history(ticker: str, period_or_dates: dict) -> pd.DataFrame:
    """Fetch one symbol without yf.download's process-global multi-ticker state.
    The result is empty, or has ``(ticker, field)`` MultiIndex columns."""
    # These are DEFAULTS the caller may override via period_or_dates. Merging (rather
    # than splatting alongside fixed kwargs) avoids "got multiple values for keyword
    # argument 'auto_adjust'" when a caller passes auto_adjust in the dict (seed /
    # forward-returns / archive paths all do).
    params = {"actions": False, "auto_adjust": price_auto_adjust(), "timeout": 30}
    params.update(period_or_dates)
    data = yf.Ticker(ticker).history(**params)
    if data is None or data.empty:
        return pd.DataFrame()
    if not isinstance(data.columns, pd.MultiIndex):
        data.columns = pd.MultiIndex.from_product([[ticker], data.columns])
    return _drop_adj_close(data)


def _download_once(batch: list[str], period_or_dates: dict) -> pd.DataFrame:
    if len(batch) == 1:
        return _single_ticker_history(batch[0], period_or_dates)
    # no uncontrolled yfinance inner threads; pool + throttle govern concurrency.
    # Defaults overridable by period_or_dates (same anti-collision reason as above).
    params = {"group_by": "ticker", "threads": False, "progress": False, "timeout": 30,
              "auto_adjust": price_auto_adjust()}
    params.update(period_or_dates)
    return _drop_adj_close(yf.download(batch, **params))


def _download_batch_with_retry(batch: list[str], period_or_dates: dict | str,
                               max_retries: int = 3) -> pd.DataFrame:
    """
    Download a batch of tickers with automatic retry on failure.
    ``period_or_dates`` is either a period string ('5y') or a dict of yfinance
    window kwargs ({'period': ...} / {'start': ..., 'end': ...}).
    Returns the downloaded DataFrame (possibly empty on total failure).
    """
    if isinstance(period_or_dates, str):
        period_or_dates = {"period": period_or_dates}
    for attempt in range(1, max_retries + 1):
        try:
            rate_limit.throttle(len(batch))  # shared global outbound-rate ceiling
            batch_data = _download_once(batch, period_or_dates)
            # A multi-ticker download reports its per-symbol failures, a 429
            # among them, out of band in yfinance's error table.
            error_text = _last_yahoo_batch_error_text(batch) if len(batch) > 1 else ""
            if not batch_data.empty:
                if _is_yahoo_rate_limit_text(error_text):
                    rate_limit.note_rate_limit(_rate_limit_backoff_seconds())
                return batch_data
            if attempt < max_retries and _is_yahoo_rate_limit_text(error_text):
                wait = _retry_wait_seconds(attempt, error_text=error_text)
                print(f"    Attempt {attempt}/{max_retries} rate-limited. Retrying in {wait:g}s...")
                time.sleep(wait)
                continue
            return pd.DataFrame()
        except Exception as e:
            if _is_yahoo_no_history_error(e):
                return pd.DataFrame()
            if attempt < max_retries:
                wait = _retry_wait_seconds(attempt, e)
                print(f"    Attempt {attempt}/{max_retries} failed ({e}). Retrying in {wait:g}s...")
                time.sleep(wait)
            else:
                print(f"    Batch failed after {max_retries} retries: {e}")

    return pd.DataFrame()


def _batched_download(tickers: list[str], period_or_dates: dict, label: str) -> pd.DataFrame:
    """Download ``tickers`` one request at a time through a BOUNDED, rate-limited
    pool. ``period_or_dates`` is either ``{'period': '2y'}`` (full refetch) or
    ``{'start': date, 'end': date}`` (incremental).

    Each ticker is a single-ticker request (``Ticker.history``) gated by the shared token bucket
    (``core.pipeline.market_data.rate_limit``), and the pool size caps simultaneous
    connections — so the concurrent workers collectively respect ONE outbound-rate
    ceiling instead of bursting Yahoo into 429s. This replaces the old 500-batch
    ``threads=True`` path whose uncontrolled inner threads (one per ticker, each
    throttling independently) were the root cause of the rate-limit storms.
    """
    if not tickers:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    total = len(tickers)
    done = 0
    workers = min(rate_limit.download_workers(), total)
    print(f"  {label}: {total} tickers via {workers} rate-limited workers...", flush=True)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_download_batch_with_retry, [ticker], period_or_dates): ticker
            for ticker in tickers
        }
        for fut in as_completed(futures):
            frame = fut.result()
            done += 1
            if not frame.empty:
                frames.append(frame)
            if done % 500 == 0 or done == total:
                print(f"    {label}: {done}/{total} fetched ({len(frames)} non-empty)...", flush=True)

    if not frames:
        return pd.DataFrame()

    data = pd.concat([_drop_index_tz(frame) for frame in frames], axis=1)
    if isinstance(data.columns, pd.MultiIndex):
        data = data.loc[:, ~data.columns.duplicated(keep='last')]
    return data

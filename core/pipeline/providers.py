"""Market-data provider abstraction.

The screener reads its canonical daily-bar panel through a ``MarketDataProvider``,
never directly from a named vendor. Today the only provider is Yahoo (yfinance),
which simply wraps the incumbent ``fetch_data`` path verbatim. The interface
exists so a bulk-EOD vendor (EODHD, Polygon, ...) can be slotted in behind the
same contract and validated against Yahoo with ``tools/provider_parity.py``
*before* it ever feeds a real or archiveable scan.

Why this matters for Chrollo specifically: the engine's structural thresholds
(box geometry off High/Low, the LPS/descent-tail/traversal floors) are calibrated
against the exact adjusted series the incumbent returns. A different vendor's
split/dividend adjustment can shift those reads, so swapping providers is a
*recalibration* event, not a clean infra swap — hence the contract below pins the
panel shape AND the adjustment convention, and the parity harness gates the swap
on engine output, not just on prices matching.

Canonical panel shape (the contract every provider must satisfy):
  - index:   tz-naive ``DatetimeIndex`` of trading sessions, ascending
  - columns: pandas ``MultiIndex`` of ``(ticker, field)``
  - fields:  ``Open``, ``High``, ``Low``, ``Close``, ``Volume`` (and ``Adj Close``
             iff the incumbent carries it). If the active engine reads adjusted
             prices, a new provider MUST follow the SAME adjustment convention as
             the incumbent so the calibrated thresholds keep their meaning.
  - window:  the full ``settings.DOWNLOAD_PERIOD`` trailing history for every
             requested ticker, plus ``settings.INDEX_SYMBOLS`` (the screener pulls
             market-regime context from the same panel).
"""
from __future__ import annotations

import threading
from typing import Optional, Protocol

import pandas as pd

from config import settings


# yfinance's ``.info``/``.calendar`` and single-symbol ``.download`` make untimed
# page scrapes that routinely hang for tens of seconds or wedge entirely; the
# library's own per-request ``timeout`` is unreliable. A hung call on a web
# request path stalls the one worker thread that serves everyone. The archive
# writer already guards its ``.info``/SPY+VIX fetches with this exact daemon-thread
# pattern (see ``webapp/backend/archive_models.py``); the provider centralizes it
# so every hang-prone vendor call shares one hard wall-clock bound.
_INFO_TIMEOUT_S = 12  # bound for per-symbol ``.info``/``.calendar`` scrapes
_DOWNLOAD_TIMEOUT_S = 25  # bound for a single-symbol candle download


def _run_bounded(fn, timeout_s: float, default=None):
    """Run ``fn()`` on a daemon thread, returning its result or ``default`` if it
    has not finished within ``timeout_s`` seconds. The thread is abandoned (not
    killed) on timeout — acceptable because every guarded callee is a read-only
    network scrape with no side effects.

    A vendor failure inside ``fn`` (yfinance raising on a delisted/sparse symbol)
    is an *operational* error every existing call site already degrades to a
    missing quote: it is caught and mapped to ``default`` so one bad symbol never
    propagates out of the bounded read. Programmer errors in the calling code are
    unaffected — they surface at the call site, not inside this thread.
    """
    holder: dict = {}

    def _run():
        try:
            holder["r"] = fn()
        except Exception:  # operational: vendor/network failure → degrade to default
            holder["r"] = default

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout_s)
    return holder.get("r", default)


class MarketDataProvider(Protocol):
    """Structural contract for a daily-bar source. See module docstring for the
    canonical panel shape every implementation must return from ``fetch``."""

    name: str

    def fetch(self, tickers: list[str]) -> pd.DataFrame:
        """Return the canonical panel for ``tickers`` (+ index symbols)."""
        ...

    def daily_candles(self, symbol: str, days: int) -> pd.DataFrame:
        """Return a single-level-column daily OHLCV frame for ``symbol`` over the
        trailing ``days`` window (UI chart panels, not the engine read)."""
        ...

    def latest_price(self, symbols: list[str]) -> dict[str, float]:
        """Return ``{symbol: last_price}`` for the given symbols (live quote)."""
        ...

    def sector(self, ticker: str) -> Optional[str]:
        """Return the raw Yahoo sector label for ``ticker`` (or ``None``)."""
        ...

    def earnings_date(self, ticker: str) -> Optional[str]:
        """Return the next earnings date (ISO ``YYYY-MM-DD``) or ``None``."""
        ...

    def info(self, ticker: str) -> dict:
        """Return the raw yfinance ``.info`` dict for ``ticker`` (or ``{}``)."""
        ...

    def get_income_stmt(self, ticker: str, *, quarterly: bool = True) -> pd.DataFrame:
        """Return the (quarterly) income statement frame for ``ticker``.

        Columns are period-end dates (most-recent-first, as yfinance ships them);
        rows are line items (``Total Revenue``, ``Diluted EPS``, ...). Empty frame
        on miss. Modern yfinance surface (``Ticker.income_stmt`` /
        ``Ticker.quarterly_income_stmt``) — NOT the broken legacy
        ``.quarterly_financials`` property."""
        ...

    def get_earnings_dates(self, ticker: str, limit: int = 12) -> pd.DataFrame:
        """Return the earnings-history frame for ``ticker`` (reported + estimate
        + surprise columns), most-recent-first. Empty frame on miss. Modern
        ``Ticker.get_earnings_dates(...)`` surface — NOT the broken legacy
        ``.earnings`` / ``.quarterly_earnings`` properties."""
        ...

    def index_context(self, as_of: str) -> dict:
        """Return ``{'spy_trend', 'vix_level'}`` market context as of a date."""
        ...

    def sector_trend(self, etf: str, as_of: str) -> Optional[str]:
        """Return BULLISH/BEARISH/NEUTRAL for a sector ETF as of a date."""
        ...


class YahooProvider:
    """yfinance-backed provider — a thin delegation to the incumbent path.

    Wrapping (not reimplementing) ``fetch_data`` keeps the move behind the
    interface byte-for-byte a no-op: same parquet cache, same incremental and
    split-probe logic, same output. ``downloads`` (and therefore ``yfinance``) is
    imported lazily so selecting a different provider never pays yfinance's import
    cost.
    """

    name = "yahoo"

    def fetch(self, tickers: list[str]) -> pd.DataFrame:
        from core.pipeline.downloads import fetch_data

        return fetch_data(tickers)

    # ── Capability methods (UI / enrichment, not the engine read) ──────────
    # These wrap the hang-prone single-symbol yfinance surfaces the web layer
    # used to call raw. They are deliberately separate from ``fetch``: the
    # incumbent engine panel above stays byte-identical.

    def daily_candles(
        self,
        symbol: str,
        days: int,
        *,
        start: str | None = None,
        end: str | None = None,
        auto_adjust: bool = False,
    ) -> pd.DataFrame:
        """Daily OHLCV candles for one ``symbol`` with single-level columns.

        Window: ``start``/``end`` (ISO strings) when given, else the trailing
        ``period=f"{days}d"``. ``auto_adjust`` follows the caller (UI chart
        panels want unadjusted; the archive overlay wants adjusted then rescales
        stored R/S itself). A flattened single-level column index is returned so
        callers read ``Open``/``High``/``Low``/``Close``/``Volume`` directly.
        The single-symbol download is hard-bounded against a yfinance hang.
        """
        import yfinance as yf

        def _download() -> pd.DataFrame:
            if start is not None or end is not None:
                return yf.download(
                    symbol, start=start, end=end,
                    progress=False, auto_adjust=auto_adjust,
                )
            return yf.download(
                symbol, period=f"{days}d", interval="1d",
                progress=False, auto_adjust=auto_adjust,
            )

        raw = _run_bounded(_download, _DOWNLOAD_TIMEOUT_S)
        if raw is None or raw.empty:
            return pd.DataFrame()
        if hasattr(raw.columns, "nlevels") and raw.columns.nlevels > 1:
            raw.columns = raw.columns.get_level_values(0)
        return raw

    def latest_price(self, symbols: list[str]) -> dict[str, float]:
        """Per-symbol last price via yfinance fast_info/info, each call bounded.

        Returns only the symbols that resolved; a hung or failed symbol is simply
        absent (callers treat absence as "no quote"), never a stall.
        """
        out: dict[str, float] = {}
        for symbol in symbols:
            value = _run_bounded(
                lambda s=symbol: self._last_price_impl(s), _INFO_TIMEOUT_S
            )
            if value is not None:
                out[symbol] = value
        return out

    @staticmethod
    def _last_price_impl(symbol: str) -> Optional[float]:
        import yfinance as yf

        ticker_obj = yf.Ticker(symbol)
        value = ticker_obj.fast_info.get("lastPrice") or ticker_obj.info.get("currentPrice")
        return round(float(value), 2) if value else None

    def sector(self, ticker: str) -> Optional[str]:
        """Raw Yahoo sector label for ``ticker`` (e.g. 'Technology'), bounded."""
        return _run_bounded(lambda: self._sector_impl(ticker), _INFO_TIMEOUT_S)

    @staticmethod
    def _sector_impl(ticker: str) -> Optional[str]:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        sector = info.get("sector", "")
        return sector or None

    def earnings_date(self, ticker: str) -> Optional[str]:
        """Next earnings date (ISO ``YYYY-MM-DD``) or ``None``, bounded."""
        return _run_bounded(lambda: self._earnings_date_impl(ticker), _INFO_TIMEOUT_S)

    @staticmethod
    def _earnings_date_impl(ticker: str) -> Optional[str]:
        import yfinance as yf

        cal = yf.Ticker(ticker).calendar
        if cal is None:
            return None
        earnings_date = None
        # yfinance has shipped a few shapes for `calendar` — handle dict + DataFrame.
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                earnings_date = ed[0] if isinstance(ed, (list, tuple)) and ed else ed
        elif hasattr(cal, "loc") and "Earnings Date" in getattr(cal, "index", []):
            row = cal.loc["Earnings Date"]
            earnings_date = row.iloc[0] if hasattr(row, "iloc") else row
        if earnings_date is None:
            return None
        if hasattr(earnings_date, "strftime"):
            return earnings_date.strftime("%Y-%m-%d")
        return str(earnings_date)[:10]

    # ── Fundamentals accessors (Lane C) ────────────────────────────────────
    # The fundamentals layer (core/fundamentals) reads ONLY through these three
    # surfaces. They wrap the MODERN yfinance API — ``.info``,
    # ``Ticker.quarterly_income_stmt``, ``Ticker.get_earnings_dates(...)`` — and
    # deliberately avoid the legacy ``.earnings`` / ``.quarterly_financials`` /
    # ``.quarterly_earnings`` properties, which return empty frames in current
    # yfinance. Each call reuses the existing ``_run_bounded`` daemon-thread wall
    # so one hung scrape can't stall a universe sweep; a miss degrades to ``{}`` /
    # an empty frame, never an exception.

    def info(self, ticker: str) -> dict:
        """Raw yfinance ``.info`` dict for ``ticker`` (``{}`` on miss), bounded."""
        result = _run_bounded(lambda: self._info_impl(ticker), _INFO_TIMEOUT_S)
        return result if result is not None else {}

    @staticmethod
    def _info_impl(ticker: str) -> dict:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        return dict(info) if info else {}

    def get_income_stmt(self, ticker: str, *, quarterly: bool = True) -> pd.DataFrame:
        """Quarterly (or annual) income-statement frame for ``ticker``.

        Empty frame on miss. Uses ``Ticker.quarterly_income_stmt`` /
        ``Ticker.income_stmt`` (modern surface), bounded against a hang."""
        result = _run_bounded(
            lambda: self._income_stmt_impl(ticker, quarterly), _INFO_TIMEOUT_S
        )
        return result if result is not None else pd.DataFrame()

    @staticmethod
    def _income_stmt_impl(ticker: str, quarterly: bool) -> pd.DataFrame:
        import yfinance as yf

        obj = yf.Ticker(ticker)
        stmt = obj.quarterly_income_stmt if quarterly else obj.income_stmt
        if stmt is None or getattr(stmt, "empty", True):
            return pd.DataFrame()
        return stmt

    def get_earnings_dates(self, ticker: str, limit: int = 12) -> pd.DataFrame:
        """Earnings-history frame (reported EPS, estimate, surprise) for
        ``ticker``, most-recent-first; empty frame on miss. Uses
        ``Ticker.get_earnings_dates(limit=...)`` (modern surface), bounded."""
        result = _run_bounded(
            lambda: self._earnings_dates_impl(ticker, limit), _INFO_TIMEOUT_S
        )
        return result if result is not None else pd.DataFrame()

    @staticmethod
    def _earnings_dates_impl(ticker: str, limit: int) -> pd.DataFrame:
        import yfinance as yf

        frame = yf.Ticker(ticker).get_earnings_dates(limit=limit)
        if frame is None or getattr(frame, "empty", True):
            return pd.DataFrame()
        return frame

    def index_context(self, as_of: str) -> dict:
        """SPY trend + VIX level as of ``as_of`` (ISO date), each fetch bounded.

        Returns ``{'spy_trend': str|None, 'vix_level': float|None}``. SPY trend is
        BULLISH/BEARISH/NEUTRAL off the 200-day SMA with a ±2% band; the window
        pulls 400 calendar days so the rolling(200) clears the NaN warm-up.
        """
        result = _run_bounded(lambda: self._index_context_impl(as_of), _DOWNLOAD_TIMEOUT_S)
        return result if result is not None else {"spy_trend": None, "vix_level": None}

    @staticmethod
    def _index_context_impl(as_of: str) -> dict:
        import yfinance as yf

        result = {"spy_trend": None, "vix_level": None}
        end = pd.Timestamp(as_of) + pd.Timedelta(days=5)
        start = pd.Timestamp(as_of) - pd.Timedelta(days=400)
        spy = yf.download("SPY", start=start.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), progress=False, timeout=30)
        if not spy.empty:
            spy_close = spy["Close"]
            if hasattr(spy_close, "columns"):
                spy_close = spy_close.iloc[:, 0]
            sma200 = spy_close.rolling(200).mean()
            mask = spy.index <= pd.Timestamp(as_of)
            if mask.any():
                idx = spy.index[mask][-1]
                price = float(spy_close.loc[idx])
                ma = float(sma200.loc[idx]) if not pd.isna(sma200.loc[idx]) else None
                if ma is not None:
                    if price > ma * 1.02:
                        result["spy_trend"] = "BULLISH"
                    elif price < ma * 0.98:
                        result["spy_trend"] = "BEARISH"
                    else:
                        result["spy_trend"] = "NEUTRAL"
        vix = yf.download("^VIX",
                          start=(pd.Timestamp(as_of) - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), progress=False, timeout=30)
        if not vix.empty:
            vix_close = vix["Close"]
            if hasattr(vix_close, "columns"):
                vix_close = vix_close.iloc[:, 0]
            mask = vix.index <= pd.Timestamp(as_of)
            if mask.any():
                result["vix_level"] = round(float(vix_close.loc[vix.index[mask][-1]]), 2)
        return result

    def sector_trend(self, etf: str, as_of: str) -> Optional[str]:
        """BULLISH/BEARISH/NEUTRAL for a sector ETF vs its 50-day SMA, bounded."""
        return _run_bounded(lambda: self._sector_trend_impl(etf, as_of), _DOWNLOAD_TIMEOUT_S)

    @staticmethod
    def _sector_trend_impl(etf: str, as_of: str) -> Optional[str]:
        import yfinance as yf

        end = pd.Timestamp(as_of) + pd.Timedelta(days=5)
        start = pd.Timestamp(as_of) - pd.Timedelta(days=120)
        data = yf.download(etf, start=start.strftime("%Y-%m-%d"),
                           end=end.strftime("%Y-%m-%d"), progress=False, timeout=30)
        if data.empty:
            return None
        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        sma50 = close.rolling(50).mean()
        mask = data.index <= pd.Timestamp(as_of)
        if not mask.any():
            return None
        idx = data.index[mask][-1]
        price = float(close.loc[idx])
        ma = float(sma50.loc[idx]) if not pd.isna(sma50.loc[idx]) else None
        if ma is None:
            return None
        if price > ma * 1.01:
            return "BULLISH"
        elif price < ma * 0.99:
            return "BEARISH"
        return "NEUTRAL"


# Registry of name -> provider class. New vendors register here once their
# adapter passes tools/provider_parity.py against the incumbent.
_PROVIDERS: dict[str, type] = {
    YahooProvider.name: YahooProvider,
}


def available_providers() -> list[str]:
    """Sorted list of registered provider names."""
    return sorted(_PROVIDERS)


def get_provider(name: str | None = None) -> MarketDataProvider:
    """Return the configured market-data provider instance.

    Resolution order: explicit ``name`` arg, then ``settings.MARKET_DATA_PROVIDER``,
    then ``"yahoo"``. ``settings`` is read lazily here (not at import) to respect
    the backend's config-shadowing constraint.
    """
    key = (name or getattr(settings, "MARKET_DATA_PROVIDER", "yahoo") or "yahoo").lower()
    try:
        provider_cls = _PROVIDERS[key]
    except KeyError:
        raise ValueError(
            f"Unknown market-data provider {key!r}; "
            f"known providers: {', '.join(available_providers())}"
        ) from None
    return provider_cls()

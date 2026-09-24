"""Bounded sector and market metadata enrichment for archive records."""

# ─────────────────────────────────────────────────────────────────
# Sector ETF mapping (ticker → SPDR sector ETF)
# ─────────────────────────────────────────────────────────────────
# Uses Yahoo Finance sector data to map to the SPDR sector ETF family.

_SECTOR_TO_ETF = {
    "Technology":           "XLK",
    "Healthcare":           "XLV",
    "Financial Services":   "XLF",
    "Financials":           "XLF",
    "Consumer Cyclical":    "XLY",
    "Consumer Defensive":   "XLP",
    "Communication Services": "XLC",
    "Industrials":          "XLI",
    "Energy":               "XLE",
    "Utilities":            "XLU",
    "Real Estate":          "XLRE",
    "Basic Materials":      "XLB",
}


_SECTOR_INFO_TIMEOUT_S = 12  # hard wall-clock bound for the (untimed) .info scrape


def get_sector_etf(ticker: str) -> str | None:
    """Resolve a ticker to its SPDR sector ETF using yfinance.

    Returns the ETF symbol (e.g. 'XLK') or None on failure OR an unmapped
    sector — callers that must tell those apart (the writer's persistent
    cache) use resolve_sector_etf instead.
    """
    _ok, etf = resolve_sector_etf(ticker)
    return etf or None


def resolve_sector_etf(ticker: str) -> tuple[bool, str]:
    """Failure-distinguishing sector-ETF lookup: (ok, etf).

    ok=False on exception/timeout (transient — retry later, never cache);
    ok=True with etf == "" means the lookup COMPLETED and the sector simply
    has no SPDR mapping (safe to cache forever).

    Hard-bounded with a daemon thread: yfinance's ``.info`` makes an untimed
    page scrape that routinely hangs for tens of seconds or wedges entirely.
    The archive writer also caches the result to disk so this is only hit for
    tickers it has never resolved before.
    """
    import threading

    holder: dict = {}

    def _run():
        holder["r"] = _sector_etf_impl(ticker)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_SECTOR_INFO_TIMEOUT_S)
    r = holder.get("r")  # missing key = timeout
    if r is None:
        return False, ""
    return True, r


def _sector_etf_impl(ticker: str) -> str | None:
    # "" = completed lookup, sector unmapped; None = exception (retryable).
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "")
        return _SECTOR_TO_ETF.get(sector, "")
    except Exception:
        return None


_MARKET_CONTEXT_TIMEOUT_S = 45  # hard wall-clock bound for the SPY+VIX fetch


def get_market_context(scan_date: str) -> dict:
    """Fetch SPY trend and VIX level for a given date.

    Hard-bounded with a daemon thread: yfinance's per-request ``timeout`` is
    unreliable, and a hung SPY/VIX download here would block the whole screener
    subprocess from finishing — which is what gatekeeps the webapp's scan from
    ever surfacing results. On timeout we return an empty context and move on;
    market context is non-critical archive metadata, never worth a hang.
    """
    import threading

    holder: dict = {}

    def _run():
        holder["r"] = _market_context_impl(scan_date)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=_MARKET_CONTEXT_TIMEOUT_S)
    return holder.get("r", {"spy_trend": None, "vix_level": None})


def _history_window(symbol: str, start, end):
    """One ``Ticker.history`` fetch over ``[start, end)``.

    NOT ``yf.download``: its results round-trip through module-level globals
    (``yfinance.shared._DFS``) that collide when two FastAPI threadpool requests
    fetch at once, returning one symbol's frame under another's label. These
    readers are reachable from the manual-add route, so they take the same
    per-instance surface ``providers.daily_candles`` was migrated to. The twin
    in ``core/pipeline/market_data/providers.py`` mirrors this helper; the pair is pinned by
    tests/test_provider_capabilities.py. ``auto_adjust=True`` preserves
    ``download``'s adjusted-close default the SMA readers were calibrated
    against, and the tz-aware index ``history`` returns is stripped so the
    tz-naive ``scan_date`` masks below keep working.
    """
    import pandas as pd
    import yfinance as yf

    frame = yf.Ticker(symbol).history(
        start=pd.Timestamp(start).strftime("%Y-%m-%d"),
        end=pd.Timestamp(end).strftime("%Y-%m-%d"),
        interval="1d", auto_adjust=True, actions=False,
    )
    if frame is None:
        return pd.DataFrame()
    if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
        frame.columns = frame.columns.get_level_values(-1)
    if getattr(frame.index, "tz", None) is not None:
        frame.index = frame.index.tz_localize(None)
    return frame


def _market_context_impl(scan_date: str) -> dict:
    """Actual SPY-trend + VIX fetch. Returns {'spy_trend', 'vix_level'}."""
    import pandas as pd

    result = {"spy_trend": None, "vix_level": None}
    try:
        end = pd.Timestamp(scan_date) + pd.Timedelta(days=5)
        # SMA-200 below needs >=200 trading bars; 250 calendar days is only
        # ~172 trading days, so the rolling(200) was all-NaN and spy_trend
        # silently stayed None. 400 calendar days (~275 trading bars) clears it.
        start = pd.Timestamp(scan_date) - pd.Timedelta(days=400)

        spy = _history_window("SPY", start, end)
        if not spy.empty:
            spy_close = spy["Close"]
            if hasattr(spy_close, "columns"):
                spy_close = spy_close.iloc[:, 0]
            sma200 = spy_close.rolling(200).mean()
            # Use the bar on or just before scan_date
            mask = spy.index <= pd.Timestamp(scan_date)
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

        vix = _history_window("^VIX", pd.Timestamp(scan_date) - pd.Timedelta(days=5), end)
        if not vix.empty:
            vix_close = vix["Close"]
            if hasattr(vix_close, "columns"):
                vix_close = vix_close.iloc[:, 0]
            mask = vix.index <= pd.Timestamp(scan_date)
            if mask.any():
                result["vix_level"] = round(float(vix_close.loc[vix.index[mask][-1]]), 2)
    except Exception:
        pass

    return result


def get_sector_trend(sector_etf: str, scan_date: str) -> str | None:
    """Determine if a sector ETF is in a bullish/bearish/neutral trend on scan_date."""
    import pandas as pd

    try:
        end = pd.Timestamp(scan_date) + pd.Timedelta(days=5)
        start = pd.Timestamp(scan_date) - pd.Timedelta(days=120)

        data = _history_window(sector_etf, start, end)
        if data.empty:
            return None

        close = data["Close"]
        if hasattr(close, "columns"):
            close = close.iloc[:, 0]
        sma50 = close.rolling(50).mean()
        mask = data.index <= pd.Timestamp(scan_date)
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
    except Exception:
        return None

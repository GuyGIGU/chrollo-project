"""
Setup Archive model — persistent memory for every screener signal.

Each row captures the full structural fingerprint of a detected setup,
its scoring decomposition, market context, and (once computed) the actual
forward returns / MFE / MAE.  This is the ground-truth table that the
calibration engine uses to validate and refine the screener's parameters.
"""
from sqlalchemy import Column, Float, Integer, String, Text, UniqueConstraint

from database import Base


class SetupArchive(Base):
    __tablename__ = "setup_archive"

    id = Column(Integer, primary_key=True, index=True)

    # ── Identity ─────────────────────────────────────────────────
    ticker = Column(String, nullable=False, index=True)
    scan_date = Column(String, nullable=False, index=True)   # YYYY-MM-DD
    setup_type = Column(String, nullable=False)               # LPS / REBOUND / BREAKOUT

    # ── Screener scoring snapshot ────────────────────────────────
    tier = Column(String, nullable=False)
    score = Column(Float, nullable=False)

    # ── Structural DNA ───────────────────────────────────────────
    current_price = Column(Float)
    r_level = Column(Float)           # Resistance
    s_level = Column(Float)           # Support
    trigger_price = Column(Float)     # Entry trigger
    base_length = Column(Integer)
    box_width = Column(Float)
    touches = Column(Integer)         # r_touches + s_touches
    r_touches = Column(Integer)
    s_touches = Column(Integer)
    atr_ratio = Column(Float)
    lps_length = Column(Integer)
    breach_days = Column(Integer)
    r_anchor = Column(Integer, nullable=True)
    s_anchor = Column(Integer, nullable=True)
    vol_contraction = Column(Float)
    tightness_ratio = Column(Float)

    # ── Sub-scores (decomposed for regression) ───────────────────
    score_box_tightness = Column(Float, nullable=True)
    score_touch_density = Column(Float, nullable=True)
    score_oscillation = Column(Float, nullable=True)
    score_atr_squeeze = Column(Float, nullable=True)
    score_lps_tightness = Column(Float, nullable=True)
    score_vol_contraction = Column(Float, nullable=True)
    score_base_age = Column(Float, nullable=True)
    score_uptrend_bonus = Column(Float, nullable=True)
    score_rs_bonus = Column(Float, nullable=True)

    # ── Forward returns (populated by updater) ───────────────────
    triggered = Column(Integer, nullable=True)        # 0/1: did price reach trigger?
    trigger_date = Column(String, nullable=True)      # YYYY-MM-DD
    fwd_return_1d = Column(Float, nullable=True)
    fwd_return_5d = Column(Float, nullable=True)
    fwd_return_10d = Column(Float, nullable=True)
    fwd_return_20d = Column(Float, nullable=True)
    fwd_return_60d = Column(Float, nullable=True)
    mfe_20d = Column(Float, nullable=True)            # Max favorable excursion (20d)
    mae_20d = Column(Float, nullable=True)            # Max adverse excursion (20d)
    mfe_60d = Column(Float, nullable=True)            # Max favorable excursion (60d)
    mae_60d = Column(Float, nullable=True)            # Max adverse excursion (60d)
    mfe_20d_date = Column(String, nullable=True)      # YYYY-MM-DD when MFE 20d high was hit
    mae_20d_date = Column(String, nullable=True)      # YYYY-MM-DD when MAE 20d low was hit
    r_multiple_20d = Column(Float, nullable=True)     # MFE_20d / risk_pct — true reward/risk
    r_multiple_60d = Column(Float, nullable=True)
    trigger_volume_ratio = Column(Float, nullable=True)  # vol_on_trigger_day / Vol_50_at_scan

    # ── Market context at time of signal ─────────────────────────
    spy_trend = Column(String, nullable=True)         # BULLISH / BEARISH / NEUTRAL
    vix_level = Column(Float, nullable=True)
    sector_etf = Column(String, nullable=True)        # XLK, XLF, XLE, etc.
    sector_trend = Column(String, nullable=True)      # BULLISH / BEARISH / NEUTRAL
    rs_vs_sector_pct = Column(Float, nullable=True)   # stock_return_during_base − sector_return_during_base
    dist_52w_high_pct = Column(Float, nullable=True)  # (current − max_high_252d) / max_high_252d (negative)
    excess_return_6m = Column(Float, nullable=True)   # stock 6m return − SPY 6m return at scan_date
    breadth_pct = Column(Float, nullable=True)        # % of universe with Close > SMA_50 on scan_date

    # ── Phase A structural detail ────────────────────────────────
    bars_since_bc = Column(Integer, nullable=True)    # Bars from BC (or SC) to scan_date
    descent_length = Column(Integer, nullable=True)   # Bars from BC to AR low (or SC to bounce high)
    phase_d_inner = Column(Integer, nullable=True)    # 1 if the hierarchical detector picked an inner sub-box (Phase D launchpad), else 0

    # ── Manual curation (human-in-the-loop) ──────────────────────
    quality_label = Column(String, nullable=True)     # perfect / good / noise / miss
    notes = Column(Text, nullable=True)
    source = Column(String, default="screener")       # screener / seed / manual

    __table_args__ = (
        UniqueConstraint("ticker", "scan_date", name="uq_ticker_scan_date"),
    )


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


def get_sector_etf(ticker: str) -> str | None:
    """Resolve a ticker to its SPDR sector ETF using yfinance.

    Returns the ETF symbol (e.g. 'XLK') or None on failure.
    Cached in-memory per session since sector doesn't change.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "")
        return _SECTOR_TO_ETF.get(sector)
    except Exception:
        return None


def get_market_context(scan_date: str) -> dict:
    """Fetch SPY trend and VIX level for a given date.

    Returns dict with 'spy_trend' and 'vix_level'.
    """
    import pandas as pd
    import yfinance as yf

    result = {"spy_trend": None, "vix_level": None}
    try:
        end = pd.Timestamp(scan_date) + pd.Timedelta(days=5)
        start = pd.Timestamp(scan_date) - pd.Timedelta(days=250)

        spy = yf.download("SPY", start=start.strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), progress=False, timeout=30)
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

        vix = yf.download("^VIX", start=(pd.Timestamp(scan_date) - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
                          end=end.strftime("%Y-%m-%d"), progress=False, timeout=30)
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
    import yfinance as yf

    try:
        end = pd.Timestamp(scan_date) + pd.Timedelta(days=5)
        start = pd.Timestamp(scan_date) - pd.Timedelta(days=120)

        data = yf.download(sector_etf, start=start.strftime("%Y-%m-%d"),
                           end=end.strftime("%Y-%m-%d"), progress=False, timeout=30)
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

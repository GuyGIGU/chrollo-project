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

    # ── Triple-barrier outcome label (path events + derived win/loss/timeout) ──
    # Anchored to the scan close. Stop = s_level*0.97; targets = entry+2.5*risk
    # and entry*1.15. Raw event timings stored so the label can be re-cut later.
    days_to_trigger = Column(Integer, nullable=True)  # bars from scan to trigger touch (1-based)
    days_to_2_5r = Column(Integer, nullable=True)     # bars to 2.5R profit target (None = never)
    days_to_15pct = Column(Integer, nullable=True)    # bars to +15% profit target (None = never)
    days_to_stop = Column(Integer, nullable=True)     # bars to stop (low <= s_level*0.97; None = never)
    barrier_label = Column(String, nullable=True)     # win / loss / timeout (target-before-stop race)
    win_barrier = Column(String, nullable=True)       # 2.5R / 15pct — which target fired first on a win

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

    # ── Volume-around-touches signature (Wyckoff no-supply / spring test) ──
    r_touch_vol_z = Column(Float, nullable=True)      # z-score of avg volume at R-touches vs base volume distribution. Negative = no supply, positive = distribution warning.
    s_touch_vol_z = Column(Float, nullable=True)      # z-score of avg volume at S-touches. Positive = spring strength (heavy hands defending), negative = weak support.

    # ── LPS shape & zone detail ──────────────────────────────────
    lps_descent_frac = Column(Float, nullable=True)   # Pair-wise descent fraction across LPS lows (0=rally, 0.5=sideways, 1=clean descent)
    lps_zone_type = Column(String, nullable=True)     # INSIDE / OVERSHOOT_R / UNDERCUT_S — splits LPS quality by structural role
    score_high_proximity = Column(Float, nullable=True)  # 52w-high proximity sub-score (raw points)
    score_breadth_bonus = Column(Float, nullable=True)   # Market-breadth bonus sub-score (raw points)

    # ── VCP progressive-contraction footprint ────────────────────
    contraction_count = Column(Integer, nullable=True)       # number of peak->valley contractions in the base
    contraction_quality = Column(Float, nullable=True)       # [0,1] composite: count + progressive tightening + final tightness
    final_contraction_depth = Column(Float, nullable=True)   # depth of the last (rightmost) contraction, fractional
    score_contraction = Column(Float, nullable=True)         # contraction-quality sub-score (raw points)
    base_median_spread_atr = Column(Float, nullable=True)     # median base spread / ATR snapshot
    base_p80_spread_atr = Column(Float, nullable=True)        # 80th percentile base spread / ATR snapshot
    base_median_spread_pct_box = Column(Float, nullable=True) # median base spread / box height
    base_tight_bar_pct = Column(Float, nullable=True)         # share of base bars with spread <= ATR snapshot

    # ── Ascending support / higher-lows footprint ────────────────
    support_slope_atr = Column(Float, nullable=True)         # ATR-normalized slope of zigzag valley lows (positive = rising support)
    ascending_support_quality = Column(Float, nullable=True) # [0,1] composite: slope ramp + higher-low consistency
    score_ascending_support = Column(Float, nullable=True)   # ascending-support sub-score (raw points)

    # ── ADR% absolute-volatility character ──────────────────────
    adr_pct = Column(Float, nullable=True)                    # Average Daily Range % over 20 bars (plain percent)
    score_adr = Column(Float, nullable=True)                  # ADR sub-score (raw points)

    # ── Phase-D scoping layer (descriptive right-most-region bands) ──
    # Read-only measurement: where each region begins + the LPS support band.
    # Dates align with the chart OHLC; archived raw for the fidelity harness.
    scope_phase_a_date = Column(String, nullable=True)  # Phase A (climax/lead-in) start
    scope_phase_b_date = Column(String, nullable=True)  # Phase B (equilibrium body) start
    scope_phase_d_date = Column(String, nullable=True)  # Phase D (right-most launchpad) start
    scope_phase_c_date = Column(String, nullable=True)  # Phase C spring marker (UNDERCUT_S only)
    scope_has_mini = Column(Integer, nullable=True)     # 1 if Phase D is an inner mini-consolidation
    scope_confidence = Column(Float, nullable=True)     # [0,1] fraction of regions confidently placed

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


_SECTOR_INFO_TIMEOUT_S = 12  # hard wall-clock bound for the (untimed) .info scrape


def get_sector_etf(ticker: str) -> str | None:
    """Resolve a ticker to its SPDR sector ETF using yfinance.

    Returns the ETF symbol (e.g. 'XLK') or None on failure.

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
    return holder.get("r")


def _sector_etf_impl(ticker: str) -> str | None:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        sector = info.get("sector", "")
        return _SECTOR_TO_ETF.get(sector)
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


def _market_context_impl(scan_date: str) -> dict:
    """Actual SPY-trend + VIX fetch. Returns {'spy_trend', 'vix_level'}."""
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

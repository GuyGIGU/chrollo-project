"""Event-study CAR curves with calendar-time-portfolio standard errors.

The screener emits SPARSE EVENTS (a "fire" on a ticker on a date), so the right
edge lens is an EVENT STUDY: for each fire, the cumulative ABNORMAL return
(ticker return minus SPY return over the same window) at horizons t = 1..K bars.
CAR(t) answers "how much excess-vs-market does a fire deliver, and does that grow
with horizon?"

THE CLUSTERING TRAP (and the fix). A good screener fires MORE names on the same
strong-tape days, so same-date fires are positively cross-correlated. The naive
cross-sectional standard error (treat every fire as independent) is therefore
biased DOWNWARD and its t-stat inflated. The fix is the **calendar-time
portfolio**: collapse all fires sharing a scan_date into ONE portfolio observation
for that date, then compute the mean / SE / t-stat on the TIME SERIES of per-date
portfolio abnormals. Each date contributes one observation regardless of how many
names fired — cross-sectional dependence within a day can no longer inflate
significance. We report BOTH the calendar-time and the naive cross-sectional
t-stats so the inflation is visible, and treat calendar-time as authoritative.

Refs: Kothari & Warner, *Econometrics of Event Studies*; the calendar-time
portfolio approach (Jaffe 1974; Mitchell & Stafford 2000) for event clustering.

Two layers:
  * ``fire_abnormal_returns`` — reads forward price paths from a cache panel and
    builds the per-fire CAR(t) table. The only layer that touches price data.
  * ``aggregate_calendar_time`` / ``build_event_study`` — PURE aggregation over
    that table (DataFrame in, dict out). Trivially unit-testable with synthetic
    abnormal-return frames, no price data needed.

All stats are NaN-safe and deterministic.
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

DEFAULT_HORIZONS: tuple[int, ...] = (1, 5, 10, 20, 40, 60)
SPY_SYMBOL = "SPY"


# ─────────────────────────────────────────────────────────────────────────────
# Layer 1 — per-fire CAR(t) from a price panel (the only price-touching code)
# ─────────────────────────────────────────────────────────────────────────────
def _close_series(panel: pd.DataFrame, ticker: str) -> Optional[pd.Series]:
    """Extract a single ticker's Close series from a (Multi)Index OHLC panel."""
    try:
        if isinstance(panel.columns, pd.MultiIndex):
            sub = panel[ticker]
        else:
            sub = panel
    except KeyError:
        return None
    if "Close" not in sub:
        return None
    close = sub["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return close.dropna()


def fire_abnormal_returns(
    fires: pd.DataFrame,
    panel: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    spy_symbol: str = SPY_SYMBOL,
    ticker_col: str = "ticker",
    date_col: str = "scan_date",
) -> pd.DataFrame:
    """Per-fire cumulative abnormal return (ticker − SPY) at each horizon.

    For each fire (ticker, scan_date):
        CAR(h) = (P_tkr[h] / P_tkr[0] − 1) − (P_spy[h] / P_spy[0] − 1)
    where P[0] is the close ON the scan bar and P[h] is the close h TRADING BARS
    later (aligned by the TICKER's own forward sessions, with SPY read on those
    same dates). A horizon with no available forward bar for a fire is left NaN
    (a recent fire simply hasn't matured that far).

    Returns a frame with the fire's identity/segment columns carried through
    (``ticker``, ``scan_date``, and any of ``tier`` / ``spy_trend`` / ``setup_type``
    present) plus one ``car_{h}`` column per horizon.
    """
    horizons = sorted({int(h) for h in horizons if int(h) > 0})
    max_h = horizons[-1] if horizons else 0
    spy = _close_series(panel, spy_symbol)

    carry = [c for c in (ticker_col, date_col, "tier", "spy_trend", "setup_type")
             if c in fires.columns]
    rows: list[dict] = []
    # Cache each ticker's Close series once (many fires per ticker).
    close_cache: dict[str, Optional[pd.Series]] = {}
    for r in fires.itertuples(index=False):
        ticker = getattr(r, ticker_col, None)
        scan_date = getattr(r, date_col, None)
        if ticker is None or scan_date is None:
            continue
        if ticker not in close_cache:
            close_cache[ticker] = _close_series(panel, str(ticker))
        tkr = close_cache[ticker]
        row = {c: getattr(r, c, None) for c in carry}
        for h in horizons:
            row[f"car_{h}"] = np.nan
        if tkr is None or spy is None:
            rows.append(row)
            continue
        ts = pd.Timestamp(scan_date)
        # Entry = the ticker's close on/at the scan bar; forward = strictly after.
        on = tkr.index <= ts
        if not on.any():
            rows.append(row)
            continue
        entry_ts = tkr.index[on][-1]
        p0 = float(tkr.loc[entry_ts])
        fwd = tkr[tkr.index > entry_ts]
        if p0 <= 0 or fwd.empty:
            rows.append(row)
            continue
        # SPY entry aligned by DATE (the same entry bar date), forward on the
        # ticker's forward session dates.
        spy_on = spy.index <= entry_ts
        if not spy_on.any():
            rows.append(row)
            continue
        s0 = float(spy.loc[spy.index[spy_on][-1]])
        if s0 <= 0:
            rows.append(row)
            continue
        for h in horizons:
            if len(fwd) < h:
                continue
            fwd_ts = fwd.index[h - 1]
            ph = float(fwd.iloc[h - 1])
            spy_upto = spy[spy.index <= fwd_ts]
            if spy_upto.empty:
                continue
            sh = float(spy_upto.iloc[-1])
            row[f"car_{h}"] = (ph / p0 - 1.0) - (sh / s0 - 1.0)
        rows.append(row)
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
# Layer 2 — PURE aggregation (calendar-time portfolio vs naive cross-section)
# ─────────────────────────────────────────────────────────────────────────────
def _stat_block(values: np.ndarray) -> dict:
    """mean / SE / t / n for a 1-D array, NaN-safe. SE/t None if n < 2."""
    v = values[~np.isnan(values)]
    n = int(v.size)
    if n == 0:
        return {"mean": None, "se": None, "t": None, "n": 0}
    mean = float(v.mean())
    if n < 2:
        return {"mean": mean, "se": None, "t": None, "n": n}
    se = float(v.std(ddof=1) / np.sqrt(n))
    t = float(mean / se) if se > 0 else None
    return {"mean": mean, "se": se, "t": t, "n": n}


def aggregate_calendar_time(
    abn: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    date_col: str = "scan_date",
) -> dict:
    """Aggregate a per-fire abnormal-return frame at each horizon.

    For every ``car_{h}`` column returns:
      * calendar-time portfolio: collapse same-``scan_date`` fires to one mean per
        date, then mean / SE / t over the per-date series (``*_ct``, ``n_dates``);
      * naive cross-section: mean / SE / t over all fires (``*_cs``, ``n_fires``).
    The calendar-time block is authoritative; the cross-section is shown only to
    expose the clustering inflation (``t_cs`` will exceed ``t_ct`` when fires
    cluster on strong-tape days).
    """
    horizons = sorted({int(h) for h in horizons if int(h) > 0})
    out: dict[int, dict] = {}
    for h in horizons:
        col = f"car_{h}"
        if col not in abn.columns:
            continue
        vals = pd.to_numeric(abn[col], errors="coerce")
        cs = _stat_block(vals.to_numpy(dtype=float))
        # Calendar-time: mean per date, then stats over the date-level series.
        if date_col in abn.columns:
            tmp = pd.DataFrame({date_col: abn[date_col].astype(str), col: vals}).dropna()
            per_date = tmp.groupby(date_col)[col].mean()
            ct = _stat_block(per_date.to_numpy(dtype=float))
        else:
            ct = {"mean": cs["mean"], "se": None, "t": None, "n": cs["n"]}
        out[h] = {
            "car_mean_ct": ct["mean"], "se_ct": ct["se"], "t_ct": ct["t"],
            "n_dates": ct["n"],
            "car_mean_cs": cs["mean"], "se_cs": cs["se"], "t_cs": cs["t"],
            "n_fires": cs["n"],
        }
    return out


def build_event_study(
    abn: pd.DataFrame,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    segment_cols: Sequence[str] = ("tier", "spy_trend"),
    date_col: str = "scan_date",
) -> dict:
    """Full event-study result: overall + one CAR term-structure per segment.

    ``segment_cols`` are sliced independently (e.g. by tier AND by regime). A
    segment value with no rows is skipped. Returns::

        {
          "horizons": [...],
          "overall": {h: {car_mean_ct, se_ct, t_ct, n_dates,
                          car_mean_cs, se_cs, t_cs, n_fires}, ...},
          "by_tier":     {tier:  {h: {...}}},
          "by_spy_trend":{trend: {h: {...}}},
        }
    """
    horizons = sorted({int(h) for h in horizons if int(h) > 0})
    result: dict = {
        "horizons": horizons,
        "overall": aggregate_calendar_time(abn, horizons, date_col=date_col),
    }
    for seg in segment_cols:
        if seg not in abn.columns:
            continue
        by: dict[str, dict] = {}
        for key in sorted(abn[seg].dropna().unique(), key=str):
            sub = abn[abn[seg] == key]
            if sub.empty:
                continue
            by[str(key)] = aggregate_calendar_time(sub, horizons, date_col=date_col)
        result[f"by_{seg}"] = by
    return result

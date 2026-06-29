"""Per-ticker ADVISORY metadata (Lane E wiring).

A single null-safe entry point, ``per_ticker_advisory``, that the live evaluation
pass calls AFTER a setup has already fired geometrically. It computes the
flag-gated advisory layers that are knowable from one ticker alone:

  * fundamentals (the 5 metrics, point-in-time via ``as_of``) — flag
    ``FUNDAMENTALS_ENABLED``;
  * the RS line vs SPY + its new-high flag — flag ``RS_LINE_ENABLED``;
  * ``days_to_earnings`` (next earnings date minus ``as_of``) — folded under
    ``FUNDAMENTALS_ENABLED`` (it reads the same earnings surface).

ADVISORY CONTRACT (the hard rules this layer must never break):
  * It is metadata ONLY — it never gates a setup, never changes Score/Tier. The
    caller attaches whatever this returns onto the (already-built) result dict.
  * Every flag defaults OFF; with all OFF this returns ``{}`` and makes ZERO
    provider calls, so the engine output stays byte-identical (shadow guard).
  * Null-safe by construction: a missing/short/failed read degrades to an ABSENT
    key (never a chip, never a penalty). A vendor hiccup can't raise out of here.
  * The in-house ``rs_rating`` is NOT computed here — it is a universe-relative
    percentile the screener computes in a post-pass over all firing tickers
    (``core.regime.percentile``); this module only emits the single-ticker inputs.

Flags are read LAZILY via ``getattr(settings, ...)`` to respect the backend
config/cwd shadowing constraint.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd


def _flag(name: str, default=False):
    try:
        from config import settings

        return getattr(settings, name, default)
    except Exception:  # pragma: no cover - settings import guard
        return default


def _trailing_return(df: pd.DataFrame, lookback: int) -> Optional[float]:
    """Trailing close-to-close return over ``lookback`` bars ending at the latest
    bar of ``df``; the universe-relative RS rating percentile-ranks this. ``None``
    when the frame is too short or the base close is non-positive."""
    if df is None or "Close" not in getattr(df, "columns", []) or len(df) <= lookback:
        return None
    try:
        last = float(df["Close"].iloc[-1])
        base = float(df["Close"].iloc[-lookback - 1])
    except (IndexError, TypeError, ValueError):
        return None
    if base <= 0:
        return None
    return last / base - 1.0


def _days_to_earnings(provider, ticker: str, as_of) -> Optional[int]:
    """Calendar days from ``as_of`` to the NEXT earnings date, or ``None``.

    Uses the bounded ``provider.earnings_date`` (next-earnings) surface. Negative
    or unparseable results degrade to ``None`` (a past/empty date is not a
    forward warning). This is a forward-looking calendar fact, NOT fundamentals
    history, so no filing-lag gate applies."""
    try:
        nxt = provider.earnings_date(ticker)
    except Exception:
        return None
    if not nxt:
        return None
    try:
        delta = (pd.Timestamp(nxt) - pd.Timestamp(as_of)).days
    except (TypeError, ValueError):
        return None
    return int(delta) if delta >= 0 else None


def per_ticker_advisory(
    ticker: str,
    df: pd.DataFrame,
    *,
    as_of=None,
    provider=None,
) -> dict:
    """Return the flag-gated per-ticker advisory metadata for ``ticker``.

    Keys (all OPTIONAL — only present when their flag is ON and the read
    succeeded), each ``_``-prefixed to match the result-dict / archive convention:

      FUNDAMENTALS_ENABLED:
        ``_fund_eps_growth_yoy``, ``_fund_sales_growth_yoy``,
        ``_fund_eps_growth_accel``, ``_fund_earnings_surprise``,
        ``_days_to_earnings``
      RS_LINE_ENABLED:
        ``_rs_line_latest``, ``_rs_line_new_high``
      (always, cheaply, when ANY advisory flag is on — the screener needs it to
       rank the universe RS rating):
        ``_rs_trailing_return``

    ``as_of`` defaults to the latest bar date in ``df`` (the live "today"), so the
    point-in-time fundamentals gate keys off the same bar the geometry was read on.
    """
    fundamentals_on = bool(_flag("FUNDAMENTALS_ENABLED"))
    rs_line_on = bool(_flag("RS_LINE_ENABLED"))
    if not (fundamentals_on or rs_line_on):
        return {}

    if provider is None:
        from core.pipeline.providers import get_provider

        provider = get_provider()
    if as_of is None and df is not None and len(df):
        as_of = df.index[-1]

    out: dict = {}

    # Trailing return feeds the universe RS-rating percentile in the screener
    # post-pass. Cheap (no network), so emit it whenever an advisory flag is on.
    rs_lookback = int(_flag("RS_RATING_LOOKBACK", 252) or 252)
    tr = _trailing_return(df, rs_lookback)
    if tr is not None:
        out["_rs_trailing_return"] = round(float(tr), 6)

    if fundamentals_on:
        try:
            from core.fundamentals import metrics

            m = metrics.compute_metrics(ticker, as_of=as_of, provider=provider)
            for key in ("eps_growth_yoy", "sales_growth_yoy",
                        "eps_growth_accel", "earnings_surprise"):
                if m.get(key) is not None:
                    out[f"_fund_{key}"] = round(float(m[key]), 6)
        except Exception:
            pass  # any miss -> no fundamentals keys (never a penalty)

        dte = _days_to_earnings(provider, ticker, as_of)
        if dte is not None:
            out["_days_to_earnings"] = dte

    if rs_line_on:
        try:
            from core.regime.rs_line import compute_rs_line

            rs = compute_rs_line(ticker, provider=provider)
            if rs.get("latest") is not None:
                out["_rs_line_latest"] = rs["latest"]
            if rs.get("rs_line_new_high") is not None:
                out["_rs_line_new_high"] = bool(rs["rs_line_new_high"])
        except Exception:
            pass

    return out

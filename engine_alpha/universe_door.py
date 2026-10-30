"""The universe door: the baseline gate every chart passes before it is read, ONE implementation.

Price -> 50-day volume -> SMA50 -> SMA200 -> year-over-year return, first fail names the reason. The two dark
exceptions (``SMA50_DIP_EXCEPTION_ENABLED``, ``BOTTOMING_BASE_LANE_ENABLED``, both False) ride here until their
settings are deleted with the old engine; off, the door reads exactly as it did in ``evaluation.py``.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from config import settings
from engine_alpha.metrics import calculate_atr


def _sma50_dip_admits(df: pd.DataFrame) -> bool:
    """The 50-day dip exception (``SMA50_DIP_EXCEPTION_ENABLED``, dark): admit an sma50 refusal when the dip
    under the 50-day is a bounded, recent event that has already recovered to the rail — the last close
    at/above SMA_50 printed within ``SMA50_DIP_MAX_SESSIONS``, and the close now sits within
    ``SMA50_DIP_MAX_ATR`` ATR_10 below it. Flag off -> False, byte-identical."""
    if not settings.SMA50_DIP_EXCEPTION_ENABLED:
        return False
    above = (df['Close'] >= df['SMA_50']).values
    hits = above.nonzero()[0]
    if not len(hits):
        return False                      # never above the 50-day: not a dip
    if (len(above) - 1 - int(hits[-1])) > settings.SMA50_DIP_MAX_SESSIONS:
        return False
    atr = calculate_atr(df, 10).iloc[-1]
    if pd.isna(atr) or float(atr) <= 0:
        return False
    gap = float(df['SMA_50'].iloc[-1]) - float(df['Close'].iloc[-1])
    return gap <= settings.SMA50_DIP_MAX_ATR * float(atr)


def apply_baseline_filters_with_reason(
    df: pd.DataFrame,
) -> tuple[Optional[tuple[pd.DataFrame, float]], Optional[tuple[str, dict]]]:
    """The universe baseline gate, reasoned.

    Returns ``((df, yearly_return), None)`` on pass, or ``(None, (gate,
    samples))`` naming the FIRST failing gate with the sampled values. Gate
    order price -> Vol_50 -> SMA50 -> SMA200 -> YoY is the contract: first-fail
    names the reason. Comparison forms are verbatim doctrine — a NaN sample
    passes its ``<`` gate (never add isfinite hardening here).

    The price floor runs BEFORE the rolling enrichment: Close at the latest bar
    reads off the raw frame, so a sub-``MIN_PRICE`` ticker skips the copy and
    the three rolling windows entirely. Its reject samples therefore carry only
    ``close`` — the one value that exists (and the one its consumer reads).
    """
    if len(df) < 200:
        return None, ("bars", {"bars": len(df)})

    close = df['Close'].iloc[-1]
    if close < settings.MIN_PRICE:
        return None, ("price", {"close": close})

    df = df.copy()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['Vol_50'] = df['Volume'].rolling(window=50).mean()

    df['Spread'] = df['High'] - df['Low']

    latest = df.iloc[-1]
    one_year_ago_idx = max(0, len(df) - 252)
    one_year_ago = df.iloc[one_year_ago_idx]

    yearly_return = (latest['Close'] - one_year_ago['Close']) / one_year_ago['Close']

    samples = {"close": latest['Close'], "vol_50": latest['Vol_50'],
               "sma_50": latest['SMA_50'], "sma_200": latest['SMA_200'],
               "yearly_return": yearly_return}
    if latest['Vol_50'] < settings.MIN_VOLUME_50D: return None, ("vol50", samples)
    if latest['Close'] < latest['SMA_50'] and not _sma50_dip_admits(df):
        return None, ("sma50", samples)
    # The bottoming-base lane (dark): an sma200 refusal enters chart reading when the 50-day is reclaimed.
    # NaN SMA_50 fails the >= closed — the exception never rides missing data.
    if latest['Close'] < latest['SMA_200'] and not (
            settings.BOTTOMING_BASE_LANE_ENABLED
            and latest['Close'] >= latest['SMA_50']):
        return None, ("sma200", samples)
    if yearly_return < settings.MIN_YEARLY_RETURN: return None, ("yoy", samples)

    return (df, float(yearly_return)), None


def apply_baseline_filters(df: pd.DataFrame) -> Optional[tuple[pd.DataFrame, float]]:
    """The gate without the reason: ``(df, yearly_return)`` on pass, ``None`` when filtered out.
    yearly_return is returned (not recomputed downstream) so a consumer reuses the exact value the gate used."""
    result, _ = apply_baseline_filters_with_reason(df)
    return result

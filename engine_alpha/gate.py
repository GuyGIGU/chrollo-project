"""The gate: the one way in for every caller (``evaluate_ticker``, ``scan_read``, ``run_eval_chain``, ``read_record``).

A chart passes the baseline floors (``apply_baseline_filters_with_reason``: bars, price, volume, the two averages,
the year's return) before the reader reads it; one the gate refuses is "not scanned", never read. The frame contract
comes first: a frame that is not a chart is a failed read, counted (``EVAL_ERROR``), never "not scanned".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import pandas as pd
from config import settings
from enum import Enum


class ReadFailed(ValueError):
    """The reader refused a chart: a failed read, never "no setup". A ValueError, so a caller that skips a date on a
    crash keeps doing so; one that must say why catches this first."""

@dataclass(frozen=True)
class NotRead:
    """A chart the reader would not read: its frame broke the frame contract, named with the rule and the reason.
    Never a crash and never "no setup"; only :func:`scan_read` answers with it, so the night lists it apart."""
    ticker: str
    rule: str
    reason: str

def evaluate_ticker(ticker: str, df: pd.DataFrame,
                    spy_6m_return: float = 0.0,
                    breadth_pct: Optional[float] = None,
                    *, watch: Optional[dict] = None):
    """One ticker through the gate and the reader, under the skip guard: a result dict, ``None`` (refused, or no
    setup) or ``EVAL_ERROR`` (the read failed; counted, never raised). The two market arguments are the pool's call
    shape; the reader reads neither."""

    result = _read(ticker, df, watch)[1]
    return EVAL_ERROR if isinstance(result, NotRead) else result

def scan_read(ticker: str, df: pd.DataFrame,
              spy_6m_return: float = 0.0,
              breadth_pct: Optional[float] = None):
    """The nightly pool's worker: :func:`evaluate_ticker`'s three answers, and a fourth only the scan takes, a
    :class:`NotRead` for a frame the reader would not read. Module-level, so the pool pickles it by name."""
    return _read(ticker, df, None)[1]

def _read(ticker: str, df, watch: Optional[dict]):
    """The frame contract, the gate's floors, then the reader through the result row: the ONE place it is called.
    Returns ``(read, result)``; both None when the gate refused."""
    from engine_alpha import reader, result

    refused = None
    try:
        reader.check_frame(df)
        admitted, reason = apply_baseline_filters_with_reason(df)
    except reader.FrameRefused as refusal:
        refused, admitted = refusal, None   # not a chart: the read below refuses it by name
    except Exception as exc:            # a chart the gate cannot ask about: a counted failure too
        read = reader.crashed(ticker, None, "the universe door could not read the frame: "
                                              f"{type(exc).__name__}: {exc}")
        result.fill_watch(read, watch)
        return read, result.to_result(read)
    if admitted is None and refused is None:
        if watch is not None:
            watch.update(alpha=True, state="not scanned", why=reason[0])
        return None, None
    read = result.graded_read(reader.read(ticker, df),
                                        frame=None if admitted is None else admitted[0])
    result.fill_watch(read, watch)
    if refused is not None and read.failed:
        return read, NotRead(ticker, refused.rule or str(refused), read.refusal or str(refused))
    return read, result.to_result(read, frame=None if admitted is None else admitted[0])

def run_eval_chain(ticker: str, df: pd.DataFrame,
                   spy_6m_return: float = 0.0,
                   breadth_pct: Optional[float] = None,
                   *, watch: Optional[dict] = None):
    """The chain WITHOUT the skip guard: a failed read raises :class:`ReadFailed` and the caller decides (the seed
    skips the date, the chart-state page says the read failed)."""
    read, result = _read(ticker, df, watch)
    if read is not None and read.failed:
        raise ReadFailed(f"two-eyes reader refused {ticker}: {read.refusal}")
    return result

def read_record(ticker: str, df: pd.DataFrame, *, watch: Optional[dict] = None):
    """The reader's own ``Read`` of a chart, by the scan's path, for a caller that wants the reasons, not a fire; a
    failed one says so (``failed``, ``refusal``). ``None`` when the gate refused it, with the leg in ``watch["why"]``."""
    read, _ = _read(ticker, df, watch)
    return read


def apply_baseline_filters_with_reason(
    df: pd.DataFrame,
) -> tuple[Optional[tuple[pd.DataFrame, float]], Optional[tuple[str, dict]]]:
    """The baseline floors, reasoned: ``((df, yearly_return), None)`` on pass, else ``(None, (floor, samples))``
    naming the FIRST failing floor, in the order bars -> price -> Vol_50 -> SMA50 -> SMA200 -> YoY. The comparison
    forms are doctrine: a NaN sample passes its ``<`` (never add isfinite hardening here)."""
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
    if latest['Close'] < latest['SMA_50']: return None, ("sma50", samples)
    if latest['Close'] < latest['SMA_200']: return None, ("sma200", samples)
    if yearly_return < settings.MIN_YEARLY_RETURN: return None, ("yoy", samples)

    return (df, float(yearly_return)), None

def apply_baseline_filters(df: pd.DataFrame) -> Optional[tuple[pd.DataFrame, float]]:
    """The floors without the reason: ``(df, yearly_return)`` on pass, ``None`` when refused; the same yearly_return
    the floors used, so a consumer never recomputes it."""
    result, _ = apply_baseline_filters_with_reason(df)
    return result


class _EvalSkip(Enum):
    ERROR = "error"

EVAL_ERROR = _EvalSkip.ERROR

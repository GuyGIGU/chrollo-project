"""The gate: the one way in for every caller (``evaluate_ticker``, ``scan_read``, ``run_eval_chain``,
``read_record``), the floors a stock passes before its chart is read, and the counted-failure sentinel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import pandas as pd
from config import settings
from enum import Enum


class ReadFailed(ValueError):
    """The reader refused a chart: a failed read, which is never "no setup".

    A ValueError, so every caller that already skips a date on a crash keeps
    doing so; one that must SAY why (the manual add, the seed's count) catches
    this first (council review 2026-10-09, finding 3)."""

@dataclass(frozen=True)
class NotRead:
    """A chart the reader would not read: its frame broke the frame contract (a trading day missing from the
    middle, the same day twice, ...), named, with the rule and the whole reason.

    Never a crash and never "no setup": a halted stock's gap is real, so the chart is not repaired, and the night
    lists it apart from the crashes, which alert. Only the scan's worker (:func:`scan_read`) answers with it; every
    other entry point keeps its own three answers."""
    ticker: str
    rule: str
    reason: str

def evaluate_ticker(ticker: str, df: pd.DataFrame,
                    spy_6m_return: float = 0.0,
                    breadth_pct: Optional[float] = None,
                    *, watch: Optional[dict] = None):
    """One ticker, the whole chain, under the standard skip guard.

    Returns a result dict, ``None`` (filtered out, or no setup) or ``EVAL_ERROR`` (the read failed; counted,
    never raised). The two market arguments are the pool's fixed call shape; the reader reads neither.
    """

    result = _read(ticker, df, watch)[1]
    return EVAL_ERROR if isinstance(result, NotRead) else result

def scan_read(ticker: str, df: pd.DataFrame,
              spy_6m_return: float = 0.0,
              breadth_pct: Optional[float] = None):
    """The reader's worker for the nightly scan's pool.

    :func:`evaluate_ticker`'s three answers, and a fourth only the scan takes: a chart whose frame the reader would
    not read comes back as :class:`NotRead`, by name and reason, so the night lists it apart from the crashes
    (``EVAL_ERROR``, which still alert). Module-level, so the pool pickles it by name.
    """
    return _read(ticker, df, None)[1]

def _read(ticker: str, df, watch: Optional[dict]):
    """The reader, through its adapter — the ONE place it is called.

    The universe door stands BEFORE the read, and it is the one door
    (``engine_alpha/py``, one implementation of a ruled judgment): a chart it refuses is "not
    scanned", with the leg named, and is never read. It is one of the few
    hard things in his method, and a fire that ignored it would not be a fire
    the scan could ever show. The frame contract comes before the door: a
    frame that is not a chart is a failed read, never "not scanned" — and
    it is a refusal, not a crash: the result is then a :class:`NotRead`,
    which :func:`evaluate_ticker` answers as the counted failure and the scan
    lists apart. A fire carries the stock's trend template, read on the frame
    the door admitted
    (``result.to_result``'s ``frame``).
    Returns ``(read, result)``; both None when the door refused.
    """
    from engine_alpha import reader, result

    refused = None
    try:
        reader.check_frame(df)
        admitted, reason = apply_baseline_filters_with_reason(df)
    except reader.FrameRefused as refusal:
        refused, admitted = refusal, None   # not a chart: the read below refuses it by name
    except Exception as exc:            # a chart the door cannot ask about: a counted failure too
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
    """The chain WITHOUT the skip guard — it raises, and the caller decides.

    The seed and the chart-state page use this: the seed skips the date on a
    crash, the page says the read failed. Both want the exception
    (:class:`ReadFailed`), not a sentinel.
    """
    read, result = _read(ticker, df, watch)
    if read is not None and read.failed:
        raise ReadFailed(f"two-eyes reader refused {ticker}: {read.refusal}")
    return result

def read_record(ticker: str, df: pd.DataFrame, *, watch: Optional[dict] = None):
    """The reader's own record of a chart: its boxes and its trail, for a
    caller that wants the reasons, not a fire (the workbench's "why did this
    mark miss", the health board, word recall).

    The read goes through the same path as the scan's (the frame contract,
    then the universe door, then the reader). Returns the ``Read`` — a failed
    one says so (``failed``, ``refusal``) — or ``None`` when the universe door
    refused the chart, which the reader then never read; the leg is in
    ``watch["why"]``.
    """
    read, _ = _read(ticker, df, watch)
    return read


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
    if latest['Close'] < latest['SMA_50']: return None, ("sma50", samples)
    if latest['Close'] < latest['SMA_200']: return None, ("sma200", samples)
    if yearly_return < settings.MIN_YEARLY_RETURN: return None, ("yoy", samples)

    return (df, float(yearly_return)), None

def apply_baseline_filters(df: pd.DataFrame) -> Optional[tuple[pd.DataFrame, float]]:
    """The gate without the reason: ``(df, yearly_return)`` on pass, ``None`` when filtered out.
    yearly_return is returned (not recomputed downstream) so a consumer reuses the exact value the gate used."""
    result, _ = apply_baseline_filters_with_reason(df)
    return result


class _EvalSkip(Enum):
    ERROR = "error"

EVAL_ERROR = _EvalSkip.ERROR

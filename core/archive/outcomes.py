"""Single source of truth for setup OUTCOME math.

Both the forward-return updater (``core.archive.forward_returns``) and the
backtest harness read their outcome numbers from here, so the math is computed in
exactly ONE place — no divergent re-derivation between "the column we store" and
"the edge we report".

Two families of outcome live side by side:

  * FIXED-WINDOW  (``mfe_20d`` / ``mae_20d`` / ``mfe_60d`` / ``mae_60d`` /
    ``fwd_return_*`` / ``r_multiple_*`` + the triple-barrier path events). These
    only resolve once the full N-bar window has elapsed — they are the mature,
    apples-to-apples columns the archive has always stored.

  * ELAPSED-WINDOW  (``mfe_to_date`` / ``mae_to_date`` / ``ret_to_date`` /
    ``bars_to_date`` / ``abnormal_ret_to_date``). These measure the favorable /
    adverse excursion over WHATEVER window has elapsed so far (capped at 60 bars),
    recomputed every run as the window grows. They are NEVER gated on a full
    window, so the backtest report can never get "stuck on no mature data" — it
    reads an edge today from however many bars exist, and that edge sharpens as
    the bars accumulate.

WINDOW-AGNOSTIC BY CONSTRUCTION: every function here is parameterized by the bars
it is given. There is no hardcoded "needs a full 20" precondition; a function
returns ``None`` only when there is literally no data to measure (zero forward
bars), never because a fixed horizon has not elapsed.

PURE: sequences / arrays in, a float or a plain dict out. No DB, no network, no
settings import, no pandas required (operates on plain float sequences so it is
trivially unit-testable and shared without I/O coupling).

LOOKAHEAD DISCIPLINE: every excursion is measured strictly FORWARD of the scan
bar (the caller passes only post-scan bars) and anchored to the scan close, so
the elapsed metrics share one reference frame with the fixed-window metrics and
can never read a price that predates the signal.
"""
from __future__ import annotations

from typing import Optional, Sequence

# Max forward bars any outcome — fixed OR elapsed — is ever evaluated over. Kept
# here as the single definition; forward_returns re-exports it for back-compat.
HORIZON_BARS = 60

# Stop / target geometry for the triple-barrier label (matches the screener's
# LPS_HOLD_TOLERANCE buffer the archive has always used).
STOP_TOLERANCE = 0.97        # stop sits at s_level * 0.97
TARGET_R_MULTIPLE = 2.5      # R-based profit target: entry + 2.5 * risk
TARGET_PCT = 0.15            # fixed-percent profit target: entry * 1.15


def _to_floats(seq: Sequence) -> list[float]:
    return [float(x) for x in seq]


# ─────────────────────────────────────────────────────────────────────────────
# Triple-barrier path events (moved verbatim from forward_returns; one home now)
# ─────────────────────────────────────────────────────────────────────────────
def compute_barrier_events(highs, lows, entry, s_level, horizon=HORIZON_BARS):
    """Triple-barrier path events measured forward from the scan bar.

    Walks up to ``horizon`` forward bars and records the first bar (1-based) that
    touches each barrier:
      - 2.5R profit target  (high >= entry + TARGET_R_MULTIPLE * risk)
      - +15% profit target  (high >= entry * (1 + TARGET_PCT))
      - stop                (low  <= s_level * STOP_TOLERANCE)
    where ``risk = entry - s_level * STOP_TOLERANCE`` (per share). Anchored to the
    scan close so it shares one reference frame with the existing MFE/MAE/R-multiple.

    Derives a single ``barrier_label``:
      'win'     a profit target is touched on an EARLIER bar than the stop
      'loss'    the stop is touched first. Same-bar ties resolve to loss — the
                conservative assumption for a long, since intrabar order is unknown.
      'timeout' neither barrier is touched within the horizon

    Pure: no DB, no network, no pandas required (operates on plain sequences).
    """
    empty = {
        "days_to_2_5r": None, "days_to_15pct": None, "days_to_stop": None,
        "barrier_label": None, "win_barrier": None,
    }
    if entry is None or entry <= 0 or s_level is None or s_level <= 0:
        return empty
    stop = s_level * STOP_TOLERANCE
    risk = entry - stop
    if risk <= 0:  # stop at/above entry → degenerate, can't label
        return empty

    target_r = entry + TARGET_R_MULTIPLE * risk
    target_pct = entry * (1.0 + TARGET_PCT)
    n = min(len(highs), len(lows), horizon)

    def _first(hit):
        for i in range(n):
            if hit(i):
                return i + 1  # 1-based bar count
        return None

    d_r = _first(lambda i: highs[i] >= target_r)
    d_pct = _first(lambda i: highs[i] >= target_pct)
    d_stop = _first(lambda i: lows[i] <= stop)

    target_days = [d for d in (d_r, d_pct) if d is not None]
    d_target = min(target_days) if target_days else None

    if d_target is not None and (d_stop is None or d_target < d_stop):
        label = "win"
        # which definition fired first; on a same-bar tie 2.5R is the stronger move
        win_barrier = "2.5R" if (d_r is not None and (d_pct is None or d_r <= d_pct)) else "15pct"
    elif d_stop is not None:
        label = "loss"
        win_barrier = None
    else:
        label = "timeout"
        win_barrier = None

    return {
        "days_to_2_5r": d_r,
        "days_to_15pct": d_pct,
        "days_to_stop": d_stop,
        "barrier_label": label,
        "win_barrier": win_barrier,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Elapsed-window outcome (the window-agnostic edge metric)
# ─────────────────────────────────────────────────────────────────────────────
def _excursion(extreme: float, scan_close: float) -> float:
    """Excursion of ``extreme`` from ``scan_close`` as a signed fraction."""
    return (extreme - scan_close) / scan_close


def compute_elapsed_outcome(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    scan_close: float,
    *,
    spy_window_return: Optional[float] = None,
    horizon: int = HORIZON_BARS,
) -> dict:
    """Outcome over the AVAILABLE forward window (``min(bars, horizon)``).

    Measures, over however many forward bars exist (capped at ``horizon``):
      - ``mfe_to_date``  max favorable excursion so far (fraction of scan_close)
      - ``mae_to_date``  max adverse  excursion so far (fraction of scan_close)
      - ``ret_to_date``  close-to-close return at the last available bar
      - ``bars_to_date`` forward bars used (1..horizon)
      - ``abnormal_ret_to_date``  ``ret_to_date`` minus the SPY same-window return
        (the bias control); ``None`` when no SPY window return is supplied.

    NEVER gated on a full fixed window: with 1 forward bar it returns a 1-bar read;
    with 0 forward bars (or a non-positive scan_close) it returns all-``None``.
    Holiday gaps are irrelevant — it counts AVAILABLE BARS, not calendar days, so a
    market closure simply means one fewer bar in the window, not a wrong horizon.

    Returns a dict with exactly the five keys above. Pure.
    """
    none_result = {
        "mfe_to_date": None,
        "mae_to_date": None,
        "ret_to_date": None,
        "bars_to_date": None,
        "abnormal_ret_to_date": None,
    }
    if scan_close is None or scan_close <= 0:
        return dict(none_result)

    highs = _to_floats(highs)
    lows = _to_floats(lows)
    closes = _to_floats(closes)

    n = min(len(highs), len(lows), len(closes), horizon)
    if n <= 0:
        return dict(none_result)

    window_highs = highs[:n]
    window_lows = lows[:n]
    window_closes = closes[:n]

    mfe = _excursion(max(window_highs), scan_close)
    mae = _excursion(min(window_lows), scan_close)
    ret = _excursion(window_closes[-1], scan_close)

    abnormal = None
    if spy_window_return is not None:
        abnormal = ret - float(spy_window_return)

    return {
        "mfe_to_date": round(float(mfe), 5),
        "mae_to_date": round(float(mae), 5),
        "ret_to_date": round(float(ret), 5),
        "bars_to_date": int(n),
        "abnormal_ret_to_date": round(float(abnormal), 5) if abnormal is not None else None,
    }


def window_return(closes: Sequence[float], base_close: float, *, bars: Optional[int] = None) -> Optional[float]:
    """Close-to-close return of a series over its first ``bars`` bars (or all).

    Used to derive the SPY same-window return that anchors ``abnormal_ret_to_date``
    to exactly the same elapsed horizon the setup is measured over. ``None`` when
    ``base_close`` is non-positive or there is no bar to read.
    """
    if base_close is None or base_close <= 0:
        return None
    closes = _to_floats(closes)
    if bars is not None:
        closes = closes[:bars]
    if not closes:
        return None
    return round(_excursion(closes[-1], base_close), 5)

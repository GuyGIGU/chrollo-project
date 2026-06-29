"""The five per-ticker fundamentals metrics (Lane C).

Computed from the MODERN yfinance surfaces via the provider seam:

  * ``provider.get_income_stmt(ticker, quarterly=True)`` — quarterly income
    statement; rows are line items (``Diluted EPS`` / ``Basic EPS``,
    ``Total Revenue``), columns are period-end dates MOST-RECENT-FIRST.
  * ``provider.get_earnings_dates(ticker, limit)`` — earnings history; index is
    the report datetime (most-recent-first), columns include ``EPS Estimate``,
    ``Reported EPS``, ``Surprise(%)``.

The five metrics:

  1. ``eps_growth_yoy``      — (EPS[q] - EPS[q-4]) / |EPS[q-4]|          (most recent qtr vs same qtr a year ago)
  2. ``sales_growth_yoy``    — (Rev[q] - Rev[q-4]) / |Rev[q-4]|
  3. ``eps_growth_accel``    — eps_growth_yoy(q) - eps_growth_yoy(q-1)  (is YoY growth accelerating?)
  4. ``earnings_surprise``   — most recent (Reported - Estimate) / |Estimate|, as a fraction
  5. ``rs_rating``           — caller-supplied universe percentile of the trailing return (None standalone)

Every metric is independently null-safe: a missing line item, too-shallow history
(YoY needs >= 5 quarters, acceleration needs >= 6), a zero/sign-flipped base, or a
NaN cell yields ``None`` for THAT metric only — never an exception, never
contaminating the others. Growth fractions are signed (e.g. 0.25 = +25%).

POINT-IN-TIME / LOOKAHEAD DISCIPLINE
------------------------------------
yfinance ships the income statement keyed by the quarter's PERIOD-END date and
carries NO per-quarter SEC FILING date. A quarter that ended (say) 2026-03-31 is
not public until the 10-Q is filed weeks later, so a point-in-time consumer that
read it on its period-end date would be using data that did not yet exist — the
classic fundamentals lookahead leak. Mirroring the trailing-window discipline in
``rs_line.py`` / ``sector_ranking.py`` (which only ever read bars at/before the
evaluated bar), the public entry points take an explicit ``as_of`` date and a
conservative fixed FILING LAG: a quarter is usable only when
``period_end + filing_lag <= as_of``. The lag (``settings.FUNDAMENTALS_FILING_LAG_DAYS``,
default 75 days — the SEC 10-Q deadline ceiling for a non-accelerated filer, so
the quarter is assumed unknowable until then) is a deliberate WORST-CASE: it can
make a metric ``None`` for a few weeks longer than reality, but it can NEVER admit
a quarter before it was actually filed. The earnings-history frame is gated on its
OWN report-date index (that index already IS the availability date), so only rows
reported on/before ``as_of`` contribute.

When ``as_of`` is ``None`` (the default), NO availability gate is applied and the
frames are read as-is — the pre-existing latest-quarter behavior, used by callers
that have already point-in-time-sliced their input or that explicitly want the
newest data regardless of filing lag.
"""
from __future__ import annotations

import math
from typing import Optional

import pandas as pd


# Income-statement row labels vary slightly across yfinance versions; try each.
_EPS_ROWS = ("Diluted EPS", "Basic EPS")
_REVENUE_ROWS = ("Total Revenue", "Operating Revenue")

# Conservative default filing lag if settings is unreadable (config/cwd shadowing).
_DEFAULT_FILING_LAG_DAYS = 75


def _finite(x) -> Optional[float]:
    """Coerce ``x`` to a finite float, else ``None``."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _filing_lag_days(filing_lag_days: Optional[int]) -> int:
    """Resolve the filing-lag (in days). Explicit arg wins; else read lazily from
    settings (config/cwd shadowing tolerated), else the conservative default."""
    if filing_lag_days is not None:
        return int(filing_lag_days)
    try:
        from config import settings

        return int(getattr(settings, "FUNDAMENTALS_FILING_LAG_DAYS",
                           _DEFAULT_FILING_LAG_DAYS))
    except Exception:  # pragma: no cover - settings import guard
        return _DEFAULT_FILING_LAG_DAYS


def available_income_stmt(
    stmt: pd.DataFrame,
    as_of,
    *,
    filing_lag_days: Optional[int] = None,
) -> pd.DataFrame:
    """Return ``stmt`` with only the quarters AVAILABLE as of ``as_of`` kept.

    The income-statement columns are quarter PERIOD-END dates. A quarter is
    available only when ``period_end + filing_lag <= as_of`` (the filing lag
    models the unknown SEC filing date conservatively). Column order is preserved
    (most-recent-first), so the surviving ``[0]`` is the most-recent quarter that
    was actually public on ``as_of`` — never a future / not-yet-filed quarter.

    ``as_of=None`` (or an empty/unparseable frame) -> returned unchanged. A column
    whose label cannot be parsed as a date is treated as NOT-yet-available
    (dropped) so an ambiguous header can never leak future data.
    """
    if as_of is None:
        return stmt
    if stmt is None or getattr(stmt, "empty", True):
        return stmt
    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=_filing_lag_days(filing_lag_days))
    keep = []
    for col in stmt.columns:
        period_end = pd.to_datetime(col, errors="coerce")
        # Unparseable header -> conservatively NOT available.
        if pd.isna(period_end):
            continue
        if period_end <= cutoff:
            keep.append(col)
    return stmt[keep]


def available_earnings(earnings: pd.DataFrame, as_of) -> pd.DataFrame:
    """Return ``earnings`` with only rows REPORTED on/before ``as_of`` kept.

    The earnings-history index IS the report (availability) date, so no filing-lag
    estimate is needed — a row is usable iff ``report_date <= as_of``. Order is
    preserved (most-recent-first). ``as_of=None`` / empty frame -> unchanged. A row
    whose index cannot be parsed as a date is dropped (conservatively unavailable).
    """
    if as_of is None:
        return earnings
    if earnings is None or getattr(earnings, "empty", True):
        return earnings
    cutoff = pd.Timestamp(as_of)
    idx = pd.to_datetime(earnings.index, errors="coerce")
    mask = idx.notna() & (idx <= cutoff)
    return earnings[mask]


def _signed_growth(current, base) -> Optional[float]:
    """``(current - base) / |base|`` as a signed fraction, or ``None`` when either
    side is non-finite or the base is zero. ``|base|`` keeps the sign of the
    change meaningful even when the base is negative."""
    c = _finite(current)
    b = _finite(base)
    if c is None or b is None or b == 0:
        return None
    return (c - b) / abs(b)


def _ordered_quarterly_series(stmt: pd.DataFrame, row_labels) -> list[Optional[float]]:
    """Extract a line-item row from the income statement as a POSITION-PRESERVING
    list of quarterly values ordered MOST-RECENT-FIRST (yfinance's native column
    order). Each cell is a finite float or ``None``.

    Positions are NOT compacted: a gappy (NaN) quarter stays as ``None`` at its
    own index so a YoY read keeps comparing the SAME calendar quarter a year
    apart (``[0]`` vs ``[4]``). Compacting would silently shift ``[4]`` onto the
    wrong quarter when an intermediate cell is missing; instead the specific YoY
    cells are checked for finiteness by the caller and a gap there yields ``None``.
    Empty list only if the row label is absent entirely.
    """
    if stmt is None or getattr(stmt, "empty", True):
        return []
    for label in row_labels:
        if label in stmt.index:
            row = stmt.loc[label]
            # Most-recent-first is yfinance's native column order; keep positions.
            return [_finite(v) for v in row.tolist()]
    return []


def eps_growth_yoy(stmt: pd.DataFrame) -> Optional[float]:
    """Most-recent quarterly diluted-EPS growth vs the same quarter a year ago.

    Reads the frame as-given (already point-in-time-sliced by the caller, or the
    full frame). ``compute_metrics`` applies the ``as_of`` availability gate before
    calling this so the ``[0]`` quarter is the latest one public on ``as_of``."""
    eps = _ordered_quarterly_series(stmt, _EPS_ROWS)
    if len(eps) < 5:
        return None
    return _signed_growth(eps[0], eps[4])


def sales_growth_yoy(stmt: pd.DataFrame) -> Optional[float]:
    """Most-recent quarterly revenue growth vs the same quarter a year ago."""
    rev = _ordered_quarterly_series(stmt, _REVENUE_ROWS)
    if len(rev) < 5:
        return None
    return _signed_growth(rev[0], rev[4])


def eps_growth_accel(stmt: pd.DataFrame) -> Optional[float]:
    """EPS-growth acceleration: this quarter's YoY EPS growth minus last
    quarter's YoY EPS growth. Positive = growth is speeding up. Needs >= 6
    quarters (q0 vs q4, and q1 vs q5)."""
    eps = _ordered_quarterly_series(stmt, _EPS_ROWS)
    if len(eps) < 6:
        return None
    latest = _signed_growth(eps[0], eps[4])
    prior = _signed_growth(eps[1], eps[5])
    if latest is None or prior is None:
        return None
    return latest - prior


def earnings_surprise(earnings: pd.DataFrame) -> Optional[float]:
    """Most-recent earnings surprise as a signed fraction.

    Prefers a ready ``Surprise(%)`` column (yfinance ships it as a percent, e.g.
    5.0 for +5%; converted to 0.05). Falls back to
    ``(Reported EPS - EPS Estimate) / |EPS Estimate|`` from the most-recent row
    that has BOTH a reported and an estimate value. ``None`` if neither is
    available.
    """
    if earnings is None or getattr(earnings, "empty", True):
        return None

    # yfinance returns most-recent-first; iterate rows in that order.
    if "Surprise(%)" in earnings.columns:
        for v in earnings["Surprise(%)"].tolist():
            f = _finite(v)
            if f is not None:
                return f / 100.0

    has_reported = "Reported EPS" in earnings.columns
    has_estimate = "EPS Estimate" in earnings.columns
    if has_reported and has_estimate:
        for reported, estimate in zip(
            earnings["Reported EPS"].tolist(), earnings["EPS Estimate"].tolist()
        ):
            g = _signed_growth(reported, estimate)
            if g is not None:
                return g
    return None


def compute_metrics(
    ticker: str,
    *,
    as_of=None,
    rs_rating: Optional[float] = None,
    provider=None,
    earnings_limit: Optional[int] = None,
    filing_lag_days: Optional[int] = None,
) -> dict:
    """Fetch + compute the five metrics for ``ticker`` AS OF ``as_of``.

    Returns a dict with keys ``eps_growth_yoy``, ``sales_growth_yoy``,
    ``eps_growth_accel``, ``earnings_surprise``, ``rs_rating`` — each ``float`` or
    ``None``. ``rs_rating`` is passed THROUGH (it is a universe-relative percentile
    the caller computes via ``core.regime.percentile`` over trailing returns;
    there is no single-ticker RS rating). Data is read through the provider seam;
    any miss degrades the affected metric to ``None``.

    ``as_of`` (an ISO string / Timestamp / date) enforces point-in-time safety: the
    income statement is filtered to quarters whose ``period_end + filing_lag`` is
    on/before ``as_of`` (so a not-yet-filed quarter never leaks), and the earnings
    history to rows reported on/before ``as_of``. ``as_of=None`` reads the frames
    as-is (latest data, no filing-lag gate) — the legacy behavior.
    """
    if provider is None:
        from core.pipeline.providers import get_provider

        provider = get_provider()
    if earnings_limit is None:
        from config import settings

        earnings_limit = getattr(settings, "FUNDAMENTALS_EARNINGS_HISTORY_LIMIT", 12)

    stmt = provider.get_income_stmt(ticker, quarterly=True)
    earnings = provider.get_earnings_dates(ticker, limit=earnings_limit)

    # Point-in-time gate: drop quarters / earnings rows not yet public on as_of.
    stmt = available_income_stmt(stmt, as_of, filing_lag_days=filing_lag_days)
    earnings = available_earnings(earnings, as_of)

    return {
        "eps_growth_yoy": eps_growth_yoy(stmt),
        "sales_growth_yoy": sales_growth_yoy(stmt),
        "eps_growth_accel": eps_growth_accel(stmt),
        "earnings_surprise": earnings_surprise(earnings),
        "rs_rating": _finite(rs_rating),
    }

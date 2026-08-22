"""Market-data panel freshness and latest-session coverage helpers."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class CloseCoverage:
    day: pd.Timestamp
    present: int
    total: int

    @property
    def ratio(self) -> float:
        return self.present / self.total if self.total else 0.0

    def format(self) -> str:
        return f"{self.present}/{self.total} ({self.ratio:.1%})"


def unique_symbols(symbols: list[str]) -> list[str]:
    seen = set()
    out = []
    for symbol in symbols:
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        out.append(symbol)
    return out


def _row_labels_for_date(data: pd.DataFrame, day: pd.Timestamp) -> pd.Index:
    day = pd.Timestamp(day).normalize()
    index_dates = pd.DatetimeIndex(data.index).normalize()
    return data.index[index_dates == day]


def _close_presence_on(data: pd.DataFrame, symbols: list[str], row_label) -> pd.Series:
    """Boolean Series indexed by ``symbols`` — True where the symbol has a non-NaN
    Close on ``row_label``.

    Vectorised (one ``xs`` + a single-row slice) instead of a per-symbol scalar
    ``.loc`` over the ~5.5k-column panel — and ``close_coverage_on`` runs on the
    fresh/current fast path AND after every repair/cold/incremental fetch, so the
    old loop cost tens of thousands of MultiIndex lookups per run. Preserves the
    prior scalar semantics: a duplicate ``(ticker,'Close')`` torn-merge column and
    a duplicated session row both collapse via *any-non-NaN* across the matches.
    """
    try:
        closes = data.xs("Close", axis=1, level=1)
    except KeyError:
        return pd.Series(False, index=symbols)
    row = closes.loc[[row_label]].notna().any(axis=0)   # per-column any-non-NaN
    if row.index.has_duplicates:
        row = row.groupby(level=0).any()                # OR across duplicate columns
    return row.reindex(symbols, fill_value=False)


def close_coverage_on(data: pd.DataFrame, symbols: list[str], day: pd.Timestamp) -> CloseCoverage:
    symbols = unique_symbols(symbols)
    day = pd.Timestamp(day).normalize()
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return CloseCoverage(day=day, present=0, total=len(symbols))

    labels = _row_labels_for_date(data, day)
    if len(labels) == 0:
        return CloseCoverage(day=day, present=0, total=len(symbols))

    present = int(_close_presence_on(data, symbols, labels[-1]).sum())
    return CloseCoverage(day=day, present=present, total=len(symbols))


def symbols_missing_closes_on(data: pd.DataFrame, symbols: list[str], day: pd.Timestamp) -> list[str]:
    symbols = unique_symbols(symbols)
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return symbols

    labels = _row_labels_for_date(data, day)
    if len(labels) == 0:
        return symbols

    presence = _close_presence_on(data, symbols, labels[-1])
    return [symbol for symbol in symbols if not bool(presence.get(symbol, False))]


def has_all_closes_on(data: pd.DataFrame, symbols: list[str], day: pd.Timestamp) -> bool:
    coverage = close_coverage_on(data, symbols, day)
    return coverage.total > 0 and coverage.present == coverage.total


def deep_history_ratio(data: pd.DataFrame, symbols: list[str], min_bars: int) -> float:
    """Fraction of ``symbols`` carrying at least ``min_bars`` non-NaN Close bars.

    Detects the deep-history NaN-wipe corruption shape (recent bars survive while
    multi-year history is gone) that a latest-session-only coverage check is blind
    to. Returns 1.0 when there is nothing to judge (no symbols) and 0.0 for a
    panel with no usable Close columns. Vectorised: one ``notna().sum()`` over the
    panel, so it is cheap even across the full ~5.5k-ticker universe.
    """
    symbols = unique_symbols(symbols)
    if not symbols:
        return 1.0
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return 0.0
    try:
        closes = data.xs("Close", axis=1, level=1)
    except KeyError:
        return 0.0
    # A torn-merge cache can carry a duplicate (ticker, 'Close') column (a
    # documented corruption shape — see test_patch_market_data_tolerates_duplicate
    # _base_columns). That leaves ``closes`` with duplicate labels, so
    # ``counts.get(s)`` returns a Series and ``int(Series)`` raises TypeError —
    # aborting the very fetch whose job is to refetch this corrupted cache. Dedupe
    # so each symbol maps to one count (mirrors the ~columns.duplicated dedupe the
    # cache writers already apply).
    if closes.columns.duplicated().any():
        closes = closes.loc[:, ~closes.columns.duplicated(keep="last")]
    counts = closes.notna().sum()
    deep = sum(1 for s in symbols if int(counts.get(s, 0)) >= min_bars)
    return deep / len(symbols)


def history_too_shallow(
    data: pd.DataFrame | None,
    symbols: list[str],
    *,
    min_bars: int,
    min_cov: float,
) -> bool:
    """True when the panel spans years but most ``symbols`` lost their deep
    history — the NaN-wipe corruption shape a latest-session coverage check is
    blind to.

    Single source of truth for the depth predicate shared by the downloader
    (``downloads._history_too_shallow``) and the health classifier
    (``market_data_health.compute_market_data_health``), so the bar-floor +
    coverage logic can't drift between them. Each caller still supplies its OWN
    symbol set (the downloader judges tickers+indexes, health judges eligible
    tickers) — only the predicate is shared, not the scope.

    Returns False ("can't judge / fine") when the panel is empty or shorter than
    ``min_bars`` (a short/new cache can't carry deep history and must not be
    flagged), and when deep coverage meets ``min_cov`` — so the healthy fast paths
    stay byte-identical.
    """
    if data is None or data.empty:
        return False
    if len(data.index) < min_bars:
        return False
    return deep_history_ratio(data, symbols, min_bars) < min_cov


def last_complete_reference_date(data: pd.DataFrame, symbols: list[str]) -> pd.Timestamp | None:
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return None

    for day in reversed(pd.DatetimeIndex(data.index).normalize().unique()):
        if has_all_closes_on(data, symbols, day):
            return pd.Timestamp(day).normalize()
    return None

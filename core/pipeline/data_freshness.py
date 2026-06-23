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


def _has_symbol_close(data: pd.DataFrame, symbol: str, row_label) -> bool:
    close_columns = [
        column
        for column in data.columns
        if isinstance(column, tuple) and len(column) > 1 and column[0] == symbol and column[1] == 'Close'
    ]
    if not close_columns:
        return False

    value = data.loc[row_label, data.columns.isin(close_columns)]
    if isinstance(value, pd.DataFrame):
        return bool(value.notna().to_numpy().any())
    if isinstance(value, pd.Series):
        return bool(value.notna().any())
    return not pd.isna(value)


def close_coverage_on(data: pd.DataFrame, symbols: list[str], day: pd.Timestamp) -> CloseCoverage:
    symbols = unique_symbols(symbols)
    day = pd.Timestamp(day).normalize()
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return CloseCoverage(day=day, present=0, total=len(symbols))

    labels = _row_labels_for_date(data, day)
    if len(labels) == 0:
        return CloseCoverage(day=day, present=0, total=len(symbols))

    row_label = labels[-1]
    present = sum(1 for symbol in symbols if _has_symbol_close(data, symbol, row_label))
    return CloseCoverage(day=day, present=present, total=len(symbols))


def symbols_missing_closes_on(data: pd.DataFrame, symbols: list[str], day: pd.Timestamp) -> list[str]:
    symbols = unique_symbols(symbols)
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return symbols

    labels = _row_labels_for_date(data, day)
    if len(labels) == 0:
        return symbols

    row_label = labels[-1]
    return [symbol for symbol in symbols if not _has_symbol_close(data, symbol, row_label)]


def has_all_closes_on(data: pd.DataFrame, symbols: list[str], day: pd.Timestamp) -> bool:
    coverage = close_coverage_on(data, symbols, day)
    return coverage.total > 0 and coverage.present == coverage.total


def last_complete_reference_date(data: pd.DataFrame, symbols: list[str]) -> pd.Timestamp | None:
    if data.empty or not isinstance(data.columns, pd.MultiIndex):
        return None

    for day in reversed(pd.DatetimeIndex(data.index).normalize().unique()):
        if has_all_closes_on(data, symbols, day):
            return pd.Timestamp(day).normalize()
    return None

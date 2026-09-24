"""Council #6 — close_coverage_on / symbols_missing_closes_on were vectorised
(one xs + single-row slice) off the per-symbol scalar .loc loop. These pin the
semantics the old scalar path had, including the two subtle edges the vectorised
helper must preserve: a duplicate (ticker,'Close') torn-merge column and a
duplicated session row both count as present via ANY-non-NaN across the matches.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.pipeline.market_data.data_freshness import (
    close_coverage_on,
    has_all_closes_on,
    last_complete_reference_date,
    symbols_missing_closes_on,
)


def _panel(dates, cols: dict):
    df = pd.DataFrame(cols, index=pd.DatetimeIndex(dates))
    df.columns = pd.MultiIndex.from_tuples(list(cols.keys()))
    return df


def test_coverage_basic_present_missing_and_absent():
    dates = pd.to_datetime(["2026-06-01", "2026-06-02"])
    df = _panel(dates, {
        ("AAA", "Close"): [1.0, 2.0],     # present
        ("BBB", "Close"): [3.0, np.nan],  # NaN on the target session
        ("CCC", "Open"): [1.0, 1.0],      # has no Close column
    })
    day = dates[-1]
    cov = close_coverage_on(df, ["AAA", "BBB", "ZZZ"], day)  # ZZZ absent entirely
    assert (cov.present, cov.total) == (1, 3)
    assert symbols_missing_closes_on(df, ["AAA", "BBB", "ZZZ"], day) == ["BBB", "ZZZ"]


def test_coverage_duplicate_close_column_uses_any():
    # Torn-merge shape: a second (AAA,'Close') column that is NaN on the row. The
    # first carries the value, so AAA must read present (any-non-NaN across dups).
    dates = pd.to_datetime(["2026-06-02"])
    base = _panel(dates, {("AAA", "Close"): [5.0], ("BBB", "Close"): [6.0]})
    dup = pd.DataFrame({("AAA", "Close"): [np.nan]}, index=dates)
    dup.columns = pd.MultiIndex.from_tuples([("AAA", "Close")])
    panel = pd.concat([base, dup], axis=1)
    assert panel.columns.duplicated().any()  # precondition: corrupted panel
    cov = close_coverage_on(panel, ["AAA", "BBB"], dates[-1])
    assert (cov.present, cov.total) == (2, 2)
    assert symbols_missing_closes_on(panel, ["AAA", "BBB"], dates[-1]) == []


def test_coverage_duplicate_row_label_uses_any():
    # Two rows stamped the same session; AAA non-NaN in one, BBB in the other.
    dates = pd.to_datetime(["2026-06-02", "2026-06-02"])
    df = _panel(dates, {("AAA", "Close"): [np.nan, 7.0], ("BBB", "Close"): [8.0, np.nan]})
    cov = close_coverage_on(df, ["AAA", "BBB"], pd.Timestamp("2026-06-02"))
    assert (cov.present, cov.total) == (2, 2)


def test_coverage_empty_and_flat_panel():
    empty = close_coverage_on(pd.DataFrame(), ["AAA"], pd.Timestamp("2026-06-02"))
    assert (empty.present, empty.total) == (0, 1)
    flat = pd.DataFrame({"Close": [1.0]}, index=pd.to_datetime(["2026-06-02"]))
    cov = close_coverage_on(flat, ["AAA"], pd.Timestamp("2026-06-02"))
    assert (cov.present, cov.total) == (0, 1)  # not a MultiIndex -> nothing present


def test_coverage_no_rows_for_day():
    dates = pd.to_datetime(["2026-06-01"])
    df = _panel(dates, {("AAA", "Close"): [1.0]})
    cov = close_coverage_on(df, ["AAA"], pd.Timestamp("2026-06-09"))  # no such session
    assert (cov.present, cov.total) == (0, 1)
    assert symbols_missing_closes_on(df, ["AAA"], pd.Timestamp("2026-06-09")) == ["AAA"]


def test_empty_symbol_set_is_vacuously_complete():
    # An index-less universe (commodities_etf declares index_symbols=()) names no
    # reference symbol. "Every named index closed" is COMPLETE when nothing is
    # named -- the vacuous-truth convention deep_history_ratio already states.
    # The strict reading (total > 0 and ...) made every freshness gate refuse a
    # universe that had nothing to miss.
    dates = pd.to_datetime(["2026-06-01", "2026-06-02"])
    df = _panel(dates, {("AAA", "Close"): [1.0, 2.0], ("BBB", "Close"): [3.0, 4.0]})

    assert has_all_closes_on(df, [], dates[-1]) is True
    # last_complete_reference_date is a LOOP over the predicate, so the empty set
    # now anchors on the panel's own newest complete session instead of None.
    # Note this is the panel's LAST-APPEARING complete session (the loop walks
    # reversed(index.unique())), not index.max() -- they agree only because every
    # cache writer sorts, and the divergence would err old, i.e. fail closed.
    assert last_complete_reference_date(df, []) == dates[-1]


def test_named_symbols_still_require_every_close():
    # The loosening is confined to the empty set: a universe that DOES name index
    # symbols must still carry a non-NaN Close for every one of them.
    dates = pd.to_datetime(["2026-06-01", "2026-06-02"])
    df = _panel(dates, {("SPY", "Close"): [1.0, 2.0], ("QQQ", "Close"): [3.0, np.nan]})
    last = dates[-1]

    assert has_all_closes_on(df, ["SPY"], last) is True
    assert has_all_closes_on(df, ["SPY", "QQQ"], last) is False   # QQQ Close is NaN
    assert has_all_closes_on(df, ["SPY", "IWM"], last) is False   # IWM absent entirely
    # ...and the reference-date loop still walks back to the last session where
    # every named symbol did close.
    assert last_complete_reference_date(df, ["SPY", "QQQ"]) == dates[0]

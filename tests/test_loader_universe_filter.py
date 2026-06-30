"""Task 6 — the loader's universe_type filter keeps the stock-only edge population
clean once the ETF universes also archive under source='screener'."""
from __future__ import annotations

import sqlite3

from core.backtest.loader import collapse_to_episodes, load_archive

_COLS = "id INTEGER PRIMARY KEY, ticker TEXT, scan_date TEXT, setup_type TEXT, source TEXT, universe_type TEXT"


def _con(rows):
    con = sqlite3.connect(":memory:")
    con.execute(f"CREATE TABLE setup_archive ({_COLS})")
    con.executemany(
        "INSERT INTO setup_archive (ticker, scan_date, setup_type, source, universe_type) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    con.commit()
    return con


def test_universe_type_filter_isolates_stocks():
    con = _con([
        ("AAA", "2026-06-29", "LPS", "screener", "us_equities"),
        ("XLK", "2026-06-29", "LPS", "screener", "us_sectors"),
        ("GLD", "2026-06-29", "LPS", "screener", "commodities_etf"),
    ])
    try:
        assert list(load_archive(con=con, universe_type="us_equities")["ticker"]) == ["AAA"]
        assert len(load_archive(con=con)) == 3  # no filter -> all
        # source + universe_type compose
        assert list(load_archive(con=con, source="screener", universe_type="us_sectors")["ticker"]) == ["XLK"]
    finally:
        con.close()


def test_universe_filter_is_noop_on_legacy_schema():
    # A pre-migration DB lacks the column; the filter must degrade gracefully.
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE setup_archive (id INTEGER PRIMARY KEY, ticker TEXT, scan_date TEXT, source TEXT)")
    con.execute("INSERT INTO setup_archive (ticker, scan_date, source) VALUES ('AAA','2026-06-29','screener')")
    con.commit()
    try:
        assert len(load_archive(con=con, universe_type="us_equities")) == 1
    finally:
        con.close()


def test_collapse_keeps_same_ticker_in_two_universes_separate():
    # The same ticker appearing as a stock AND an ETF on the same date must form
    # TWO episodes — episodes never span universes (the cross-universe merge bug).
    con = _con([
        ("GLD", "2026-06-29", "LPS", "screener", "us_equities"),
        ("GLD", "2026-06-29", "LPS", "screener", "commodities_etf"),
    ])
    try:
        eps = collapse_to_episodes(load_archive(con=con))
        assert len(eps) == 2
        assert set(eps["universe_type"]) == {"us_equities", "commodities_etf"}
    finally:
        con.close()


def test_collapse_null_universe_type_falls_back_not_nan():
    # Regression: pandas reads SQL NULL as np.nan (a float, and bool(nan) is True),
    # so a truthiness fallback would coerce NULL to the literal "nan" and split a
    # mixed-NULL ticker into a bogus "nan" episode separate from its us_equities
    # rows. NULL must collapse with us_equities into ONE episode (consecutive days).
    con = _con([
        ("AAA", "2026-06-01", "LPS", "screener", None),
        ("AAA", "2026-06-02", "LPS", "screener", "us_equities"),
        ("AAA", "2026-06-03", "LPS", "screener", None),
    ])
    try:
        eps = collapse_to_episodes(load_archive(con=con))
        assert len(eps) == 1, eps[["ticker", "scan_date", "universe_type"]].to_dict("records")
        assert eps.iloc[0]["scan_date"] == "2026-06-01"  # first-seen anchor preserved
    finally:
        con.close()

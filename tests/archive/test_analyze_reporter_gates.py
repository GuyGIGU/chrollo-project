"""Archive report-card hardening (council review 2026-08-22, Leach F2 + F5).

F2 — trigger-rate maturity gate: the fires' updater stamps triggered=0 from
the FIRST forward bar (0 means "not YET as of last maturation"), so a plain
mean deflates every recent segment's trigger rate by exactly the
still-maturing tail. ``_perf_row`` counts a row only once its verdict is
final: triggered=1, or triggered=0 with the full horizon elapsed
(bars_to_date >= HORIZON_BARS). Reporter-side only — no schema change, no
rewriting history.

F5 — ``load_archive`` opens the books of record through the read-only
mode=ro URI, so the tool's "never writes" docstring is enforced by the
connection itself, not by discipline.
"""
import inspect
import sqlite3
import sys

import pandas as pd

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from core.archive import analyze
from core.archive.analyze import _perf_row
from core.archive.outcomes import HORIZON_BARS


def _frame(rows):
    base = {"fwd_return_20d": 0.05, "fwd_return_60d": 0.10,
            "r_multiple_20d": 1.0}
    return pd.DataFrame([{**base, **r} for r in rows])


def test_trig_rate_counts_only_matured_verdicts():
    # touched (final the moment it happens, however young) ........ counts 1
    # untouched AND matured through the horizon ................... counts 0
    # untouched but still maturing (the 973-row live class) ....... excluded
    # never measured .............................................. excluded
    df = _frame([
        {"triggered": 1, "bars_to_date": 5},
        {"triggered": 0, "bars_to_date": HORIZON_BARS + 10},
        {"triggered": 0, "bars_to_date": HORIZON_BARS - 50},
        {"triggered": None, "bars_to_date": None},
    ])
    r = _perf_row(df)
    assert r["trig_rate"] == 0.5          # 1 of 2 FINAL verdicts — not 1/3


def test_trig_rate_none_when_no_verdict_is_final():
    # Only still-maturing zeros: the honest answer is "no rate yet",
    # never a fabricated 0%.
    df = _frame([
        {"triggered": 0, "bars_to_date": 3},
        {"triggered": 0, "bars_to_date": HORIZON_BARS - 1},
    ])
    assert _perf_row(df)["trig_rate"] is None


def test_horizon_boundary_is_inclusive():
    df = _frame([{"triggered": 0, "bars_to_date": HORIZON_BARS}])
    assert _perf_row(df)["trig_rate"] == 0.0


def test_premigration_db_without_bars_to_date_degrades_to_legacy_mean():
    # An old DB lacking bars_to_date has no maturity info — the ungated
    # legacy mean is the only computable statistic.
    df = _frame([{"triggered": 1}, {"triggered": 0}])
    assert _perf_row(df)["trig_rate"] == 0.5


def test_load_archive_reads_through_the_readonly_uri(tmp_path, monkeypatch):
    db = tmp_path / "archive.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE setup_archive "
                "(id INTEGER PRIMARY KEY, ticker VARCHAR, scan_date VARCHAR, "
                "source VARCHAR, universe_type VARCHAR)")
    con.execute("INSERT INTO setup_archive (ticker, scan_date, source, universe_type) "
                "VALUES ('AAA', '2026-06-01', 'screener', 'us_equities')")
    con.execute("INSERT INTO setup_archive (ticker, scan_date, source, universe_type) "
                "VALUES ('XLE', '2026-06-01', 'screener', 'us_sectors')")
    con.commit()
    con.close()

    monkeypatch.setattr(analyze, "_DB_PATH", str(db))
    df = analyze.load_archive()
    assert list(df["ticker"]) == ["AAA"]   # default equities scoping intact

    # The read-only contract is enforced by the CONNECTION (mode=ro URI —
    # the pattern seed_recall.load_seed_rows set), not by discipline alone.
    assert "mode=ro" in inspect.getsource(analyze.load_archive)
    ro = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        ro.execute("INSERT INTO setup_archive (ticker) VALUES ('EVIL')")
        raise AssertionError("mode=ro connection accepted a write")
    except sqlite3.OperationalError as exc:
        assert "readonly" in str(exc).lower()
    finally:
        ro.close()

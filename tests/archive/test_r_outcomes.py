"""His rolling LPS rule on hand-built bar sequences (core/archive/r_outcomes.py).

Each test is a day-by-day story: the fire night, then the walk. Days are indexed
from 0; the fire day is day 2 unless a story says otherwise, so the LPS at the fire
night can be read from the two days before it. Mutation-proven: every assertion
here was watched to FAIL under a deliberate break of the rule before it passed.
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT

_ROOT = str(REPO_ROOT)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.archive import r_outcomes as ro  # noqa: E402


def _bars(rows):
    """``rows`` = [(open, high, low, close), ...] -> (o, h, l, c, dates)."""
    arr = np.array(rows, dtype=float)
    dates = pd.bdate_range("2026-06-01", periods=len(rows))
    return arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], dates


# Day 0 tops the run; the LPS is the two receding days after it, the fire day (day 2)
# the last: highs 10.6 -> 10.4 -> 10.3, lows 10.0 -> 9.9 -> 9.95, so the Low is 9.9.
# The archived trigger names the fire day's high (10.3).
_LPS = [(10.5, 10.6, 10.0, 10.2), (10.3, 10.4, 9.9, 10.1), (10.1, 10.3, 9.95, 10.2)]
_FIRE = 2
_TRIGGER = 10.3


def _episode(after, lps=_LPS, trigger=_TRIGGER):
    o, h, l, c, dates = _bars(list(lps) + list(after))
    return ro.score_episode(o, h, l, c, dates, _FIRE, trigger)


def _quiet_day(prev_high):
    """A day that stays under yesterday's high while the Low holds."""
    return (prev_high - 0.1, prev_high - 0.05, 10.05, prev_high - 0.08)


# ───────────────────────────────────────────────────────── the walk's five endings
def test_the_day_after_the_fire_night_takes_out_the_fire_days_high_and_is_bought():
    out = _episode([(10.25, 10.6, 10.1, 10.5)] + [_quiet_day(10.6)] * 25)
    assert out["r_status"] == "bought"
    assert out["r_days_to_buy"] == 1 and out["r_buy_date"] == "2026-06-04"
    # yesterday's high plus a cent; the stop a cent under yesterday's low
    assert out["r_entry"] == pytest.approx(10.31)
    assert out["r_stop"] == pytest.approx(9.94)
    assert out["r_gap_open"] == 0
    assert out["r_lps_first_day"] == "2026-06-02" and out["r_low_at_fire"] == pytest.approx(9.9)


def test_quiet_days_make_the_lps_longer_and_roll_the_trigger_and_stop():
    # Two days stay under yesterday's high with lows above the Low: the LPS is now
    # four days long and the third day's trigger is the SECOND quiet day's high.
    quiet = [(10.2, 10.25, 10.05, 10.1), (10.1, 10.2, 10.02, 10.15)]
    out = _episode(quiet + [(10.18, 10.3, 10.1, 10.28)] + [_quiet_day(10.3)] * 25)
    assert out["r_status"] == "bought" and out["r_days_to_buy"] == 3
    assert out["r_entry"] == pytest.approx(10.21)      # 10.2 + a cent, not the fire day's 10.3
    assert out["r_stop"] == pytest.approx(10.01)       # a cent under 10.02, not under the Low


def test_a_gap_above_yesterdays_high_is_bought_at_the_open():
    out = _episode([(10.5, 10.8, 10.4, 10.7)] + [_quiet_day(10.8)] * 25)
    assert out["r_status"] == "bought"
    assert out["r_entry"] == pytest.approx(10.5) and out["r_gap_open"] == 1


def test_a_close_under_the_low_before_any_trigger_is_a_failed_lps():
    # Day 3 pokes under the Low (9.9) and closes under it: failed, no trade.
    out = _episode([(10.1, 10.2, 9.7, 9.8)] + [(9.8, 9.85, 9.6, 9.7)] * 20)
    assert out["r_status"] == "failed" and out["r_fail_date"] == "2026-06-04"
    assert out["r_entry"] is None and out["r_supper"] == "true failure"


def test_a_low_under_the_low_that_closes_above_it_only_lowers_the_low():
    # Day 3 dips to 9.8 but closes at 10.0: the LPS holds and the Low is now 9.8,
    # so day 4's close at 9.85 does NOT fail it.
    out = _episode([(10.1, 10.2, 9.8, 10.0), (10.0, 10.1, 9.82, 9.85), (9.9, 10.3, 9.85, 10.2)]
                   + [_quiet_day(10.3)] * 25)
    assert out["r_status"] == "bought" and out["r_days_to_buy"] == 3


def test_nothing_within_ten_trading_days_is_never_triggered():
    # Ten days each under the day before's high, every low above the Low.
    days = [(10.2 - 0.01 * i, 10.29 - 0.01 * i, 10.0, 10.1 - 0.005 * i) for i in range(10)]
    # Day 11 takes out the high at last: too late to count.
    out = _episode(days + [(10.3, 10.6, 10.2, 10.5)] + [_quiet_day(10.6)] * 20)
    assert out["r_status"] == "never triggered"
    assert out["r_entry"] is None


def test_a_walk_the_bars_have_not_finished_has_no_status_yet():
    out = _episode([_quiet_day(10.3), _quiet_day(10.25)])
    assert out["r_status"] is None
    assert out["r_measured_through"] == "2026-06-05"


# ───────────────────────────────────────────────────────── the fire day as a breakout
def test_a_fire_day_that_already_broke_out_is_bought_at_the_next_open_when_it_holds():
    lps = [(10.5, 10.6, 10.0, 10.2), (10.3, 10.4, 9.9, 10.1), (10.3, 10.9, 10.2, 10.8)]  # fire day > 10.4
    out = _episode([(10.7, 11.0, 10.6, 10.9)] + [_quiet_day(11.0)] * 25, lps=lps, trigger=10.4)
    assert out["r_status"] == "bought" and out["r_days_to_buy"] == 1
    assert out["r_entry"] == pytest.approx(10.7)         # the next open
    assert out["r_stop"] == pytest.approx(9.89)          # a cent under the day before the fire day's low


def test_a_fire_day_that_already_broke_out_and_gaps_further_is_fired_late():
    lps = [(10.5, 10.6, 10.0, 10.2), (10.3, 10.4, 9.9, 10.1), (10.3, 10.9, 10.2, 10.8)]
    out = _episode([(11.2, 11.5, 11.0, 11.4)] + [_quiet_day(11.5)] * 25, lps=lps, trigger=10.4)
    assert out["r_status"] == "fired late" and out["r_entry"] is None


# ───────────────────────────────────────────────────────── the last supper
def test_a_failed_lps_reclaimed_within_fifteen_days_runs_the_rule_again():
    fail = [(10.1, 10.2, 9.7, 9.8)]                       # close under the Low 9.9
    under = [(9.8, 9.85, 9.6, 9.7)] * 3                   # three days under
    reclaim = [(9.8, 10.0, 9.75, 9.95)]                   # a close back above the Low
    # stays under the reclaim day's high; its close 9.85 sits under the OLD Low (9.9)
    # but above the reclaim day's low (9.75), which is the Low now
    second_lps = [(9.9, 9.98, 9.78, 9.85)]
    buy = [(9.95, 10.1, 9.85, 10.05)]                     # takes out 9.98
    out = _episode(fail + under + reclaim + second_lps + buy + [_quiet_day(10.1)] * 25)
    assert out["r_status"] == "failed" and out["r_supper"] == "last supper"
    assert out["r_reclaim_date"] == "2026-06-10"
    assert out["r2_status"] == "bought" and out["r2_buy_date"] == "2026-06-12"
    assert out["r2_entry"] == pytest.approx(9.99) and out["r2_stop"] == pytest.approx(9.77)
    assert out["r2_mfe_20d"] is not None


def test_a_failed_lps_not_reclaimed_within_fifteen_days_is_a_true_failure():
    # exactly fifteen trading days under the Low and the bars end: a true failure, not open
    out = _episode([(10.1, 10.2, 9.7, 9.8)] + [(9.8, 9.85, 9.6, 9.7)] * 15)
    assert out["r_supper"] == "true failure" and out["r2_status"] is None


def test_a_failed_lps_still_inside_its_fifteen_days_is_open():
    out = _episode([(10.1, 10.2, 9.7, 9.8)] + [(9.8, 9.85, 9.6, 9.7)] * 5)
    assert out["r_supper"] == "open"


# ───────────────────────────────────────────────────────── scoring a bought trade
def _trade(after_buy, entry=10.0, stop=9.5):
    """Score a trade bought on day 0 of ``after_buy`` at ``entry`` with ``stop`` (1R = 0.5)."""
    arr = np.array(after_buy, dtype=float)
    h, l, c = arr[:, 0], arr[:, 1], arr[:, 2]
    return ro.score_trade(h, l, c, 0, entry, stop, len(arr) - 1)


def test_mfe_in_r_and_the_raw_gain_read_the_windows_high():
    # the window's HIGH (11.0 on day 1, which closed low) sets the MFE, not its best close (day 6)
    days = ([(11.0, 9.8, 9.9)] + [(10.2, 9.9, 10.0)] * 4 + [(10.6, 10.0, 10.55)] + [(10.2, 9.9, 10.0)] * 14
            + [(12.5, 10.0, 12.0)] + [(10.2, 9.9, 10.0)] * 39)
    out = _trade(days)
    assert out["r_mfe_20d"] == pytest.approx(2.0)          # (11.0 - 10.0) / 0.5
    assert out["r_gain_20d"] == pytest.approx(0.10)
    assert out["r_mfe_60d"] == pytest.approx(5.0)          # the 12.5 on day 21 counts on 60d only
    assert out["r_outcome_20d"] == pytest.approx(2.0) and out["r_stop_first_20d"] == 0
    assert out["r_exit_20d"] == pytest.approx(0.0)         # out at the window's close, 10.0
    assert out["r_risk_pct"] == pytest.approx(0.05)


def test_a_stop_hit_before_the_windows_high_counts_minus_one_r():
    days = [(10.2, 9.4, 9.6)] + [(10.1, 9.9, 10.0)] * 18 + [(12.0, 10.0, 11.5)]
    out = _trade(days)
    assert out["r_stop_first_20d"] == 1 and out["r_outcome_20d"] == pytest.approx(-1.0)
    assert out["r_mfe_20d"] == pytest.approx(4.0)          # what ran afterwards is still recorded
    assert out["r_exit_20d"] == pytest.approx(-1.0)
    assert out["r_best_before_stop_20d"] == pytest.approx(-1.0)   # stopped on the buy day: nothing made


def test_the_stop_and_the_windows_high_on_one_bar_count_the_stop_first():
    # Day 3 prints both the window's high (12.0, 4R) and a low under the stop: the bar does not say which came
    # first, so the stop counts first and the R made before it is day 2's 2R (the outcome, the exit and the
    # best-before-stop agree; the raw MFE still records the 4R).
    days = [(10.2, 9.9, 10.1), (11.0, 10.0, 10.8), (12.0, 9.4, 9.6)] + [(10.0, 9.5, 9.8)] * 17
    out = _trade(days)
    assert out["r_stop_first_20d"] == 1 and out["r_outcome_20d"] == pytest.approx(-1.0)
    assert out["r_exit_20d"] == pytest.approx(-1.0)
    assert out["r_best_before_stop_20d"] == pytest.approx(2.0)
    assert out["r_mfe_20d"] == pytest.approx(4.0)


def test_the_r_made_before_the_stop_is_what_the_tail_rate_reads():
    # 2R on day 2, the stop on day 5, 6R afterwards: P(>=2R) counts it, P(>=3R) does not.
    days = [(10.2, 9.9, 10.1), (11.0, 10.0, 10.8), (10.5, 9.9, 10.0), (10.2, 9.8, 9.9),
            (10.0, 9.4, 9.6)] + [(13.0, 11.0, 12.5)] * 15
    out = _trade(days)
    assert out["r_best_before_stop_20d"] == pytest.approx(2.0)
    assert out["r_outcome_20d"] == pytest.approx(-1.0)
    assert out["r_exit_20d"] == pytest.approx(-1.0)


def test_a_window_that_has_not_matured_writes_nothing_for_itself():
    out = _trade([(10.5, 9.9, 10.2)] * 19)
    assert "r_mfe_20d" not in out and "r_mfe_60d" not in out
    assert out["r_risk_pct"] == pytest.approx(0.05)


# ───────────────────────────────────────────────────────── the backfill
def _cache(path, tickers, days=40):
    """A tiny parquet cache in the live cache's shape: ('TICKER', 'Field') columns."""
    dates = pd.bdate_range("2026-06-01", periods=days)
    frames = {}
    for t in tickers:
        base = 10.0 + 0.01 * np.arange(days)
        frames[(t, "Open")] = base
        frames[(t, "High")] = base + 0.3
        frames[(t, "Low")] = base - 0.3
        frames[(t, "Close")] = base + 0.1
        frames[(t, "Volume")] = np.full(days, 1000.0)
    wide = pd.DataFrame(frames, index=pd.Index(dates, name="Date"))
    wide.columns = pd.MultiIndex.from_tuples(wide.columns)
    wide.to_parquet(path)
    return path


def test_the_backfill_leaves_a_row_without_bars_null_and_measures_the_rest(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROLLO_DB_PATH", str(tmp_path / "archive.db"))
    sys.path.insert(0, os.path.join(_ROOT, "webapp", "backend"))
    from sqlalchemy.orm import sessionmaker

    from archive_models import SetupArchive
    from database import make_sqlite_engine

    engine = make_sqlite_engine(str(tmp_path / "archive.db"))
    SetupArchive.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    for ticker in ("HAS", "GONE"):
        session.add(SetupArchive(ticker=ticker, scan_date="2026-06-03", setup_type="LPS", tier="S",
                                 score=80.0, source="screener", trigger_price=10.32))
    session.commit()
    session.close()
    engine.dispose()

    cache = _cache(tmp_path / "cache.parquet", ["HAS"])
    assert ro.update_r_outcomes(force=True, cache_path=str(cache)) == 1
    assert ro.update_r_outcomes(force=True, cache_path=str(cache)) == 1   # idempotent

    engine = make_sqlite_engine(str(tmp_path / "archive.db"))
    session = sessionmaker(bind=engine)()
    rows = {r.ticker: r for r in session.query(SetupArchive).all()}
    assert rows["HAS"].r_status == "bought" and rows["HAS"].r_measured_through == "2026-07-24"
    assert all(getattr(rows["GONE"], col) is None for col in ro.R_COLUMNS)
    session.close()
    engine.dispose()

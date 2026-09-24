"""Review report CLI (near-miss lane Task 11) — Friedman states, hermetic.

Empty is affirmative (collector state printed, silence is impossible to
mistake for a dead collector); the junk-heavy expectation prints BEFORE row
one; fired tickers hide by default and reveal under --all (the axis-5
ruling); an unknown filter aborts naming the offender; the counterfactual
line can never read as a pick.
"""
from __future__ import annotations

import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import database  # noqa: E402
from core.archive import near_miss_writer as nmw  # noqa: E402
from tools import near_miss_report as report  # noqa: E402

pytestmark = pytest.mark.regression

_MARGINS = {"width": 0.17, "respect_share": 1, "respect_run": 9,
            "crash": 0.25, "r_touches": 2, "s_touches": 1,
            "r_touch_thirds": 0, "s_touch_thirds": 0,
            "lower_dwell": -1, "upper_dwell": 3, "mid_dwell": 4,
            "coverage": 1, "traversal_count": 0, "traversal_density": 0.02}


def _row(ticker, fired=0, r=25.0, scan_date="2026-07-25"):
    return {"ticker": ticker, "scan_date": scan_date, "r_level": r,
            "s_level": r * 0.9, "r_anchor_date": "2026-06-01",
            "s_anchor_date": "2026-06-08", "window_start_date": "2026-06-01",
            "window_end_date": "2026-07-25", "pool": "strict",
            "kill_stage": "occupancy", "failing_leg": "occupancy",
            "judged_n": 30, "fired_night": fired,
            "episode_profile": "S+ S+ R^", "margins": dict(_MARGINS),
            "would_be_trigger": r, "scan_close": r * 0.95,
            "lane_ruleset": "2026-07-26.A"}


@pytest.fixture()
def lane_db(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'lane.db'}")
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=eng))
    return eng


def _run(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["near_miss_report", *argv])
    code = report.main()
    return code, capsys.readouterr().out


def test_empty_state_is_affirmative(lane_db, monkeypatch, capsys):
    nmw._ensure_table(database.engine)
    code, out = _run(monkeypatch, capsys)
    assert code == 0
    assert "0 near-misses recorded" in out
    assert "Collector flag:" in out          # dead-collector vs quiet-night


def test_expectation_precedes_rows_and_fired_hides_by_default(
        lane_db, monkeypatch, capsys):
    nmw.archive_near_miss_rows(
        [_row("AAA"), _row("BBB", fired=1), _row("CCC", r=30.0)],
        universe_type="us_equities", enable=True)

    code, out = _run(monkeypatch, capsys)
    assert code == 0
    assert out.index("floors sit where junk begins") < out.index("AAA")
    assert "BBB" not in out
    assert "fired-ticker episode(s) hidden" in out
    assert "never elected, never fired" in out
    assert "occupancy[lower_dwell -1]" in out

    _code, out_all = _run(monkeypatch, capsys, "--all")
    assert "BBB" in out_all and "[FIRED-TICKER]" in out_all


def test_filters_stamp_the_exact_set_and_unknowns_abort(
        lane_db, monkeypatch, capsys):
    nmw.archive_near_miss_rows([_row("AAA")], universe_type="us_equities",
                               enable=True)
    _code, out = _run(monkeypatch, capsys, "--ticker", "AAA")
    assert "filtered: ticker=AAA — the EXACT set scored" in out

    with pytest.raises(SystemExit):
        _run(monkeypatch, capsys, "--leg", "vibes")
    err = capsys.readouterr().err
    assert "vibes" in err                    # the offender is NAMED


def test_filtered_to_zero_is_affirmative_not_a_crash(
        lane_db, monkeypatch, capsys):
    """The advertised drill (--ticker EGBN before EGBN has a row) must print
    an affirmative zero, never a ValueError traceback (review 2026-07-26
    finding 3 — the one empty state the battery missed)."""
    nmw.archive_near_miss_rows([_row("AAA")], universe_type="us_equities",
                               enable=True)
    code, out = _run(monkeypatch, capsys, "--ticker", "EGBN")
    assert code == 0
    assert "0 episode(s) match [ticker=EGBN]" in out
    assert "exact set scored is empty" in out


def test_outcomes_flag_surfaces_the_payoff_cohort(lane_db, monkeypatch, capsys):
    """The banner names forward outcomes as the payoff; --outcomes gives that
    cohort a bounded surface instead of an --all dig (review finding 12)."""
    import archive_models
    nmw.archive_near_miss_rows([_row("AAA"), _row("DDD", r=40.0)],
                               universe_type="us_equities", enable=True)
    db = database.SessionLocal()
    row = db.query(archive_models.NearMissArchive).filter_by(ticker="DDD").one()
    row.bars_to_date = 60
    row.mfe_to_date = 0.12
    row.ret_to_date = 0.05
    row.triggered = 0
    db.commit()
    db.close()
    code, out = _run(monkeypatch, capsys, "--outcomes")
    assert code == 0
    assert "DDD" in out and "AAA" not in out
    assert "outcomes-only" in out
    assert "untouched" in out                # the outcome line renders


def test_new_badge_reference_night_survives_filtering(
        lane_db, monkeypatch, capsys):
    """NEW means the UNFILTERED cohort's latest night in every view — a
    drill must not re-baseline days-old episodes as NEW (review finding 12)."""
    nmw.archive_near_miss_rows([_row("CCC", r=30.0, scan_date="2026-07-24")],
                               universe_type="us_equities", enable=True)
    nmw.archive_near_miss_rows([_row("AAA")],
                               universe_type="us_equities", enable=True)
    _code, out = _run(monkeypatch, capsys, "--ticker", "CCC")
    assert "CCC" in out and "NEW" not in out
    assert "seen 1x" in out

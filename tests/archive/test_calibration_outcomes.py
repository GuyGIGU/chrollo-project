"""His calibration setups as archived setups (operator ruling 2026-10-03) — hermetic.

A calibration setup is measured exactly like a fire (the fires' own
``_compute_returns``), from the trading day before his trigger, with his support
as the stop's rail; it lands in its own table and every study reads it as its
own group, never pooled into the engine's fires. No network: the batched
download and the per-ticker frames are faked; the DB is a throwaway sqlite file.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from _paths import REPO_ROOT as ROOT
BACKEND_DIR = ROOT / "webapp" / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import archive_models  # noqa: E402
import database  # noqa: E402
from core.archive import analyze_report as report  # noqa: E402
from core.archive import calibration_outcomes as co  # noqa: E402
from core.archive import forward_returns as fr  # noqa: E402
from core.pipeline.market_data import downloads as dl  # noqa: E402

pytestmark = pytest.mark.regression

_MARKS_DDL = (
    "CREATE TABLE calibration_marks (id INTEGER PRIMARY KEY, ticker TEXT, "
    "as_of_date TEXT, label TEXT, verdict TEXT, resistance REAL, support REAL, "
    "box_start_date TEXT, trigger_date TEXT, trigger_price REAL, "
    "anchor_close REAL, revision INTEGER)"
)


def _frame(start="2026-03-02", n=90, close=10.0, cross_day="2026-03-10",
           cross_high=10.5, run_from=4, run_high=11.6):
    """Flat bars at ``close``; his trigger crossed on ``cross_day``; the
    ``run_from``-th forward bar after the cross reaches ``run_high``."""
    idx = pd.bdate_range(start, periods=n)
    highs = np.full(n, close + 0.1)
    cross = idx.get_loc(pd.Timestamp(cross_day))
    highs[cross] = cross_high
    highs[cross + run_from] = run_high
    return pd.DataFrame({"Open": close, "High": highs, "Low": close - 0.2,
                         "Close": close, "Volume": 1e6}, index=idx)


def _mark(**kw):
    mark = {"id": 1, "ticker": "EGBN", "as_of_date": "2026-03-12",
            "support": 9.5, "trigger_date": "2026-03-10", "trigger_price": 10.2,
            "anchor_close": 10.0, "revision": 1}
    mark.update(kw)
    return mark


# ── the anchor: the bar before his buy ───────────────────────────────────────
def test_the_clock_starts_on_the_bar_before_his_trigger_day():
    idx = pd.bdate_range("2026-03-02", periods=20)
    assert co.outcome_anchor(idx, _mark(trigger_date="2026-03-10")) == (
        pd.Timestamp("2026-03-09"), "trigger")
    # A Monday buy: the clock starts on the Friday before.
    assert co.outcome_anchor(idx, _mark(trigger_date="2026-03-16"))[0] == pd.Timestamp("2026-03-13")
    # No trigger marked: his as-of bar (a Saturday as-of reads the Friday).
    assert co.outcome_anchor(idx, _mark(trigger_date=None, as_of_date="2026-03-14")) == (
        pd.Timestamp("2026-03-13"), "as_of")
    # A frame that starts on his buy day holds no bar before it.
    assert co.outcome_anchor(idx, _mark(trigger_date="2026-03-02")) is None


# ── one meaning: measured with the fires' own function ───────────────────────
def test_a_calibration_setup_is_measured_exactly_like_a_fire():
    df = _frame()
    # His as-of bar closes away from the anchor bar: the entry is the ANCHOR close.
    df.loc[pd.Timestamp("2026-03-12"), "Close"] = 10.3
    values = co.measure_mark(df, _mark(anchor_close=10.3))
    anchor = pd.Timestamp("2026-03-09")
    fire = fr._compute_returns(df[df.index > anchor], 10.0, 10.2, s_level=9.5,
                               vol_50_at_scan=None)
    for key, value in fire.items():
        assert values[key] == value, key
    assert values["anchor_date"] == "2026-03-09"
    assert values["anchor_basis"] == "trigger"
    assert values["entry_close"] == 10.0
    assert values["triggered"] == 1 and values["days_to_trigger"] == 1
    assert values["days_to_15pct"] == 5           # the cross is day 1, the run day 5
    assert values["barrier_label"] == "win" and values["win_barrier"] == "15pct"
    assert values["s_level"] == 9.5 and values["trigger_price"] == 10.2


def test_an_unknowable_price_scale_blanks_every_trigger_and_stop_verdict():
    # He drew it at 100 and the fresh as-of close reads 10: no split explains 10x.
    values = co.measure_mark(_frame(), _mark(anchor_close=100.0))
    for key in ("triggered", "days_to_trigger", "barrier_label", "days_to_15pct",
                "r_multiple_20d", "trigger_price", "s_level"):
        assert values[key] is None, key
    assert values["mfe_to_date"] is not None      # ratio metrics stay valid


def test_a_split_since_he_drew_it_rescales_his_trigger_and_support():
    values = co.measure_mark(
        _frame(), _mark(anchor_close=20.0, trigger_price=20.4, support=19.0))
    assert values["trigger_price"] == pytest.approx(10.2)
    assert values["s_level"] == pytest.approx(9.5)
    assert values["triggered"] == 1


def test_no_prices_or_no_forward_bar_is_unmeasured_never_guessed():
    assert co.measure_mark(pd.DataFrame(), _mark()) is None
    # Prices end on the anchor bar itself: no forward bar to measure yet.
    assert co.measure_mark(_frame().loc[:"2026-03-09"], _mark()) is None


# ── which marks a pass re-measures ───────────────────────────────────────────
class _Row:
    def __init__(self, revision=1, bars=60):
        self.mark_revision, self.bars_to_date = revision, bars


def test_a_mark_is_re_measured_when_new_redrawn_or_still_maturing():
    mark = _mark()
    assert co.needs_measure(mark, None)
    assert not co.needs_measure(mark, _Row())
    assert co.needs_measure(mark, _Row(revision=0))         # redrawn since
    assert co.needs_measure(mark, _Row(bars=59))            # inside the window
    assert co.needs_measure(mark, _Row(bars=None))
    assert co.needs_measure(mark, _Row(), force=True)


# ── the pass end to end ──────────────────────────────────────────────────────
@pytest.fixture
def cal_db(tmp_path, monkeypatch):
    path = tmp_path / "cal.db"
    eng = create_engine(f"sqlite:///{path}")
    monkeypatch.setattr(database, "make_sqlite_engine", lambda _path: eng)
    with eng.begin() as conn:
        conn.execute(text(_MARKS_DDL))
        conn.execute(text(
            "INSERT INTO calibration_marks VALUES "
            "(1, 'EGBN', '2026-03-12', 'classic', 'box', 10.6, 9.5, '2026-02-02', '2026-03-10', 10.2, 10.0, 1),"
            "(2, 'GONE', '2026-03-12', '', 'box', 10.6, 9.5, '2026-02-02', '2026-03-10', 10.2, 10.0, 1),"
            "(3, 'NOPE', '2026-03-12', '', 'no_structure', NULL, NULL, NULL, NULL, NULL, 10.0, 1)"))
    calls = []
    monkeypatch.setattr(dl, "_batched_download",
                        lambda tickers, params, label: calls.append(tickers) or {"raw": 1})
    monkeypatch.setattr(fr, "_ticker_frame",
                        lambda raw, ticker: _frame() if ticker == "EGBN" else pd.DataFrame())
    return path, eng, calls


def test_the_pass_measures_his_box_marks_and_leaves_the_unpriced_blank(cal_db):
    path, eng, _calls = cal_db
    co._ensure_table(eng)
    with eng.begin() as conn:                     # a deleted mark's leftover outcome
        conn.execute(text("INSERT INTO calibration_outcomes (mark_id, ticker, "
                          "mark_revision, anchor_date, anchor_basis, entry_close, "
                          "computed_at) VALUES (99, 'OLD', 1, '2026-01-02', "
                          "'trigger', 5.0, 'x')"))
    assert co.update_calibration_outcomes() == 1
    rows = {r.mark_id: r for r in sessionmaker(bind=eng)().query(
        archive_models.CalibrationOutcome).all()}
    assert set(rows) == {1}                       # 99 dropped, GONE unpriced, NOPE not a box
    assert rows[1].triggered == 1 and rows[1].mark_revision == 1
    assert rows[1].bars_to_date == 60


def test_a_matured_mark_is_left_alone_until_he_redraws_it(cal_db):
    path, eng, calls = cal_db
    assert co.update_calibration_outcomes() == 1
    assert co.update_calibration_outcomes() == 0  # EGBN matured; GONE still unpriced
    assert calls[-1] == ["GONE", "SPY"]
    with eng.begin() as conn:
        conn.execute(text("UPDATE calibration_marks SET revision = 2 WHERE id = 1"))
    assert co.update_calibration_outcomes() == 1
    row = sessionmaker(bind=eng)().get(archive_models.CalibrationOutcome, 1)
    assert row.mark_revision == 2


def test_a_redrawn_mark_keeps_nothing_from_its_old_measurement(cal_db, monkeypatch):
    path, eng, _calls = cal_db
    co.update_calibration_outcomes()
    row = sessionmaker(bind=eng)().get(archive_models.CalibrationOutcome, 1)
    assert row.fwd_return_60d is not None
    # Redrawn with a buy late in the frame: under 60 forward bars, so no 60-day read.
    with eng.begin() as conn:
        conn.execute(text("UPDATE calibration_marks SET revision = 2, "
                          "trigger_date = '2026-06-25', as_of_date = '2026-06-25' WHERE id = 1"))
    late = _frame(cross_day="2026-06-25", run_from=1)
    monkeypatch.setattr(fr, "_ticker_frame",
                        lambda raw, ticker: late if ticker == "EGBN" else pd.DataFrame())
    assert co.update_calibration_outcomes() == 1
    row = sessionmaker(bind=eng)().get(archive_models.CalibrationOutcome, 1)
    assert row.anchor_date == "2026-06-24"
    assert row.fwd_return_60d is None and row.mfe_60d is None


def test_the_shared_loader_lists_every_box_mark_tagged_as_its_own_group(cal_db):
    path, eng, _calls = cal_db
    assert co.load_calibration_setups(str(path)).empty   # no outcome table yet
    co.update_calibration_outcomes()
    df = co.load_calibration_setups(str(path)).set_index("mark_id")
    assert sorted(df.index) == [1, 2]
    assert (df["source"] == "calibration").all()
    assert df.loc[1, "his_trigger_date"] == "2026-03-10"
    assert df.loc[1, "trigger_date"] == "2026-03-10"     # the day it was CROSSED
    assert df.loc[2, "ticker"] == "GONE" and pd.isna(df.loc[2, "mfe_to_date"])


# ── every study keeps them a group of their own ──────────────────────────────
def _fires():
    return pd.DataFrame({"source": ["screener"] * 3 + ["seed"] * 2,
                         "tier": ["A", "B", "A", "S", "S"],
                         "mfe_to_date": [0.05, 0.10, 0.02, 0.9, 0.8],
                         "mfe_20d": [0.04, 0.08, 0.02, 0.5, 0.5],
                         "barrier_label": ["loss", "win", "timeout", "win", "win"]})


def _calibration():
    return pd.DataFrame({"source": ["calibration"] * 2, "mfe_to_date": [0.4, 0.3],
                         "mfe_20d": [0.3, 0.2], "barrier_label": ["win", None]})


def test_the_report_card_prints_them_beside_the_fires_never_pooled():
    report._LINES.clear()
    report.section_calibration(_fires(), _calibration())
    lines = {line.split()[0] + " " + line.split()[1]: line.split()
             for line in report._LINES if line.startswith(("engine fires", "calibration setups"))}
    assert lines["engine fires"][2] == "3"        # screener only: seed and his are out
    assert lines["calibration setups"][2] == "2"
    report._LINES.clear()


def test_the_edge_tile_carries_them_beside_the_tiers_never_inside(monkeypatch):
    from domains.archive import edge

    # One reader's fires (the tile reads one reader at a time since Mon 12/10/2026);
    # the scan day and row id say which reader wrote the latest scan.
    fires = _fires().assign(scan_date="2026-10-09", id=range(1, 6))
    monkeypatch.setattr(edge, "load_episodes_by_reader",
                        lambda universe_type=None: {"new": fires.iloc[0:0], "old": fires})
    monkeypatch.setattr(edge, "load_calibration_setups", lambda: _calibration())
    out = edge._compute()
    assert out["n_unbiased"] == 3
    assert sum(b["n"] for b in out["by_tier"].values()) == 3
    assert out["calibration"]["n"] == 2 and out["calibration"]["mfe_n"] == 2
    monkeypatch.setattr(edge, "load_calibration_setups", lambda: pd.DataFrame())
    assert edge._compute()["calibration"] is None


def test_the_archive_screen_route_sorts_with_unmeasured_last(monkeypatch):
    from domains.archive.browse import list_calibration_setups

    rows = pd.DataFrame({"mark_id": [1, 2, 3], "ticker": ["A", "B", "C"],
                         "as_of_date": ["2026-03-01"] * 3,
                         "his_trigger_date": ["2026-03-01", "2026-04-01", "2026-02-01"],
                         "mfe_to_date": [0.2, None, 0.5]})
    monkeypatch.setattr(co, "load_calibration_setups", lambda: rows)
    assert [r["ticker"] for r in list_calibration_setups("mfe_to_date", "desc")] == ["C", "A", "B"]
    # A key his rows do not carry (the engine list's 'tier') falls back to his buy day.
    assert [r["ticker"] for r in list_calibration_setups("tier", "desc")] == ["B", "A", "C"]


# ── it rides the nightly outcome job, contained ──────────────────────────────
def test_a_failing_calibration_pass_never_raises_into_the_fires_run(monkeypatch):
    def boom(force=False):
        raise RuntimeError("db locked")
    monkeypatch.setattr(co, "update_calibration_outcomes", boom)
    assert fr.run_calibration_maturation() == -1


def test_the_scheduled_run_matures_them_after_the_fires(monkeypatch):
    from types import SimpleNamespace

    import app.core_settings as core_settings_mod
    import services.scan_status as scan_status_mod
    from services import scan_runner

    order = []
    monkeypatch.setattr(scan_runner, "_run_scan_process_unlocked",
                        lambda *a, **k: SimpleNamespace(output="ok", returncode=0,
                                                        n_setups=1, n_errored=0, n_refused=0))
    monkeypatch.setattr(scan_runner, "_result_status", lambda r: "ok")
    monkeypatch.setattr(scan_runner, "_tail_error", lambda out: None)
    monkeypatch.setattr(scan_runner, "alert_if_needed", lambda *a, **k: None)
    monkeypatch.setattr(scan_status_mod, "start_run", lambda trigger, kind="scan": 1)
    monkeypatch.setattr(scan_status_mod, "finish_run", lambda *a, **k: None)
    monkeypatch.setattr(core_settings_mod, "load_core_settings",
                        lambda: SimpleNamespace(FORWARD_RETURNS_MIN_AGE_DAYS=5))

    def fires(min_age_days=5):
        order.append("fires")
        raise RuntimeError("the fires' pass failed")
    monkeypatch.setattr(fr, "update_forward_returns", fires)
    monkeypatch.setattr(fr, "run_calibration_maturation",
                        lambda force=False: order.append("calibration") or 0)
    scan_runner.run_scheduled_scan_and_forward_returns()
    assert order == ["fires", "calibration"]      # runs even when the fires' pass fails


def test_the_table_is_registered_for_boot_migrations_at_birth():
    from app.migrations import additive

    assert "calibration_outcomes" in {name for name, _ in additive._MIGRATED_ARCHIVE_MODELS}

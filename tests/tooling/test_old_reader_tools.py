"""The research tools and the old-engine audits say what they read (go-live plan, task 4).

Two failures, both found by the plan's blind check. With the new reader switched on, the seed's re-read RAISES
``ReadFailed`` when the reader refuses a chart (a trading day missing from the middle of its history: 27 charts on
Thu 08/10/2026): the case audit crashed on it, and the backfill lost the ticker's WHOLE date grid with one warning.
And the audits that read the old engine straight, past the door, kept printing the old reader's reading with nothing
to say that tonight's screen was read by the other one.

His own chart (ALB to Mon 13/04/2026, sealed fixture bars) with one day deleted from the middle is the refused
chart, as in ``tests/archive/test_read_failed_is_said.py``. The switch is forced on inside a test only.
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from _paths import REPO_ROOT  # noqa: F401  (puts the repo root on the path)

CHART = "ALB:2026-04-13"
NOTICE = "reads the OLD reader"


def _his_chart():
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    return frames[CHART]


def _with_a_hole(df):
    return df.drop(df.index[len(df) // 2])


@pytest.fixture()
def new_reader(monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)


class _Stop(Exception):
    """Raised where the tool would first read its data: everything printed before it was printed FIRST."""


def _stop(*args, **kwargs):
    raise _Stop()


# --------------------------------------------------------------------------- #
# The case audit                                                              #
# --------------------------------------------------------------------------- #
def test_the_case_audit_says_the_read_failed_on_each_date_instead_of_crashing(new_reader, capsys):
    from tools.audits import structure_case_audit as audit

    off, res, sl, failed = audit.find_last_valid(_with_a_hole(_his_chart()), 0.0, scan_back=2)
    assert (off, res, sl) == (None, None, None)
    assert failed == 3
    said = capsys.readouterr().out
    assert said.count("the read failed") == 3 and "missing from the middle" in said


# --------------------------------------------------------------------------- #
# The backfill                                                                #
# --------------------------------------------------------------------------- #
def _grid_worker(monkeypatch, frame, grid):
    from tools.research import backtest_backfill as bb

    monkeypatch.setattr(bb, "_W_CACHE", pd.concat({"AAA": frame}, axis=1))
    monkeypatch.setattr(bb, "_W_SPY_FRAME", None)
    monkeypatch.setattr(bb, "_W_GRID", list(grid))
    monkeypatch.setattr(bb, "_W_SPY6", {})
    return bb


def test_the_backfill_keeps_a_refused_tickers_other_dates_and_counts_the_refused(monkeypatch):
    """Every other date of the grid is a fire here; the refused ones are counted with their reason, and the
    ticker's fires are kept. (The fire is a stand-in: the question is what the worker does around a refusal.)"""
    from engine_alpha import reader

    frame = _his_chart()
    grid = list(frame.index[-7:-1])
    refused_days = set(grid[1::2])

    def evaluate(df_slice, spy_6m_return=0.0):
        if df_slice.index[-1] in refused_days:
            raise reader.ReadFailed("two-eyes reader refused : a trading day is missing from the middle")
        return {"current_price": float(df_slice["Close"].iloc[-1]), "trigger_price": None, "s_level": None}

    bb = _grid_worker(monkeypatch, frame, grid)
    monkeypatch.setattr(bb, "_evaluate_at_date", evaluate)
    out = bb._eval_ticker_grid("AAA")
    assert [p["scan_date"] for p in out["fires"]] == [d.strftime("%Y-%m-%d") for d in grid[0::2]]
    assert [r.split(":")[0] for r in out["refused"]] == [d.strftime("%Y-%m-%d") for d in grid[1::2]]
    assert all("missing from the middle" in r for r in out["refused"])


def test_the_backfill_counts_the_real_readers_refusals(new_reader, monkeypatch):
    """The same, with nothing stood in: the new reader itself refuses every grid date after the hole."""
    frame = _with_a_hole(_his_chart())
    grid = list(frame.index[-3:])
    bb = _grid_worker(monkeypatch, frame, grid)
    out = bb._eval_ticker_grid("AAA")
    assert out["fires"] == [] and len(out["refused"]) == 3


# --------------------------------------------------------------------------- #
# The notice                                                                  #
# --------------------------------------------------------------------------- #
def test_the_notice_is_said_on_a_new_reader_night_and_only_then(monkeypatch, capsys):
    from config import settings
    from tools._bootstrap import say_old_reader

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", False, raising=False)
    assert say_old_reader() is None
    assert say_old_reader({"chart_data": {"OLD": {"candles": [], "R": 1.0}}}) is None
    assert capsys.readouterr().out == ""

    new_payload = {"chart_data": {"OLD": {"candles": []}, "NEW": {"candles": [], "two_eyes": {"boxes": []}}}}
    said = say_old_reader(new_payload)
    assert NOTICE in said and "payload it reads was read by the new reader" in said
    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)
    said = say_old_reader()
    assert NOTICE in said and "new reader is switched on" in said
    assert capsys.readouterr().out.count(NOTICE) == 2


def test_the_htf_audit_says_it_first(new_reader, monkeypatch, capsys):
    from tools.audits import htf_audit

    monkeypatch.setattr("sys.argv", ["htf_audit", "AAA"])
    monkeypatch.setattr(htf_audit.pd, "read_parquet", _stop)
    with pytest.raises(_Stop):
        htf_audit.main()
    assert capsys.readouterr().out.startswith("NOTE:")


def test_the_case_audit_says_it_first(new_reader, monkeypatch, capsys):
    from tools.audits import structure_case_audit as audit

    monkeypatch.setattr("sys.argv", ["structure_case_audit", "AAA"])
    monkeypatch.setattr(audit.pd, "read_parquet", _stop)
    with pytest.raises(_Stop):
        audit.main()
    assert capsys.readouterr().out.startswith("NOTE:")


def test_the_miss_lane_census_refuses_the_new_reader_before_reading_anything(new_reader, monkeypatch):
    """It reads through the door, so under the new reader its counts would be the new reader's, with the old
    reader's lane knobs flipped around reads that never look at them: refused by name, not counted."""
    from tools.research import miss_lane_census

    monkeypatch.setattr(miss_lane_census.pd, "read_parquet", _stop)
    with pytest.raises(SystemExit, match="OLD reader's dark lanes"):
        miss_lane_census.run()


def test_the_doctrine_audit_says_it_first_when_its_payload_was_read_by_the_new_reader(monkeypatch, capsys, tmp_path):
    """The switch OFF here: the payload alone says which reader read it (a new-reader fire's chart carries the
    ``two_eyes`` block), and the audit would otherwise check the old reader's reading against it in silence."""
    from config import settings
    from tools.audits import doctrine_audit

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", False, raising=False)
    payload = tmp_path / "screener_data.json"
    payload.write_text(json.dumps({"chart_data": {"AAA": {"candles": [{"time": "2026-04-13"}],
                                                          "two_eyes": {"boxes": []}}}}), encoding="utf-8")
    monkeypatch.setattr(doctrine_audit, "_PAYLOAD", str(payload))
    monkeypatch.setattr(doctrine_audit.pd, "read_parquet", _stop)
    with pytest.raises(_Stop):
        doctrine_audit.run_audit()
    assert capsys.readouterr().out.startswith("NOTE:")

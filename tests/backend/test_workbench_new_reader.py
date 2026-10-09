"""The box-only read under the new reader: the workbench says why a mark missed in the new reader's words.

Go-live plan, task 5. The workbench's "why did this mark miss" read the OLD reader's box and its trace (the box
cascade's rejects); under the new reader the door refused that read outright, so the chip had no reason at all. The
new reader carries its own trail (each step's stage and words) and its boxes: the reason now comes from there,
resolved in the backend (EC-28), never a translation of one engine into the other.

His own drawings, from the sealed fixture: NET to Tue 15/09/2026 (the new reader reads lines and no LPS yet on his
day) and ALB to Mon 13/04/2026 (with one trading day deleted from the middle, the chart the new reader refuses). The
old engine is made to explode in every test that reads under the new reader: a path that still reached it would say
so by name. The switch is forced on inside a test only.
"""
from __future__ import annotations

import sys

import pandas as pd
import pytest
from fastapi import HTTPException

from _paths import BACKEND_DIR, REPO_ROOT
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(1, str(BACKEND_DIR))

import domains.calibration.fired as fired  # noqa: E402

MISSED = ("NET", "2026-09-15")
REFUSED = ("ALB", "2026-04-13")


def _frame(ticker, as_of):
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    return frames[f"{ticker}:{as_of}"]


def _mark(ticker, as_of, **extra):
    return {"ticker": ticker, "as_of_date": as_of, "verdict": "box", **extra}


def _loader(frame):
    return lambda ticker, as_of, digest=None: frame


@pytest.fixture()
def new_reader(monkeypatch):
    """The switch on, and the old engine wired to explode."""
    from config import settings
    from engine_alpha import evaluation
    from engine_alpha.structure.narrative import reader as narrative

    def never(*a, **k):
        raise AssertionError("the OLD engine answered while the new reader was switched on")

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)
    for name in ("_evaluate_ticker", "_run_eval_chain", "_run_guarded_chain"):
        monkeypatch.setattr(evaluation, name, never)
    monkeypatch.setattr(narrative, "read_structure", never)


# --------------------------------------------------------------------------- #
# "Why did this mark miss", in the new reader's words                          #
# --------------------------------------------------------------------------- #
def test_the_miss_shows_the_new_readers_box_and_its_reason_from_its_own_trail(new_reader, monkeypatch):
    from engine_alpha import two_eyes
    from webapp.backend import frame_store

    ticker, as_of = MISSED
    frame = _frame(ticker, as_of)
    read = two_eyes.read(ticker, frame.loc[:pd.Timestamp(as_of)])
    box = next(s.saying for s in read.trail if s.stage == "box")
    lps = next(s.saying for s in read.trail if s.stage == "LPS")
    assert box.startswith("R 324.73") and "S 290.49" in box          # his box, as the new reader drew it
    assert lps.startswith("no LPS")

    monkeypatch.setattr(frame_store, "load_frame", _loader(frame))
    chip = fired._chip_from_fired(_mark(ticker, as_of), {"fired": False, "fired_window": [as_of, as_of]})
    assert chip["state"] == "miss" and chip["kind"] == "missed"
    assert chip["stage"] == "lines, no LPS yet" == read.state
    assert box in chip["detail"] and lps in chip["detail"]
    assert chip["detail"].startswith("the new reader")


def test_a_chart_the_new_reader_refused_is_a_failed_read_never_no_box(new_reader):
    ticker, as_of = REFUSED
    frame = _frame(ticker, as_of)
    holed = frame.drop(frame.index[len(frame) // 2])
    reason = fired._miss_reason(_mark(ticker, as_of), frame_loader=_loader(holed))
    assert reason["stage"] == "the read failed"
    assert "missing from the middle" in reason["detail"] and "box" not in reason["detail"]


def test_a_chart_the_universe_door_refused_is_not_scanned_never_no_box(new_reader, monkeypatch):
    from engine_alpha import evaluation

    monkeypatch.setattr(evaluation, "apply_baseline_filters_with_reason",
                        lambda df: (None, ("sma200", "under its 200-day average")))
    ticker, as_of = MISSED
    reason = fired._miss_reason(_mark(ticker, as_of), frame_loader=_loader(_frame(ticker, as_of)))
    assert reason["stage"] == "not scanned"
    assert "never read" in reason["detail"] and "sma200" in reason["detail"]


# --------------------------------------------------------------------------- #
# The old reader's reads refuse by name under the new reader                   #
# --------------------------------------------------------------------------- #
def test_the_replay_seams_knob_variants_refuse_by_name_under_the_new_reader(new_reader):
    from core.calibration import replay
    from engine_alpha import reader

    with pytest.raises(reader.NotThisReader, match="LPS_CEILING_REST_ENABLED"):
        replay.read_structure_under(None, 1.0, {"LPS_CEILING_REST_ENABLED": True})
    # The baseline variant has no knob to name: it is the old reader's box read itself, and that refuses too.
    with pytest.raises(reader.NotThisReader, match="box-only read"):
        replay.read_structure_under(None, 1.0, {})


def test_the_fired_walks_knob_variants_refuse_by_name_under_the_new_reader(new_reader):
    from domains.calibration.grading import fired_one

    ticker, as_of = MISSED
    from engine_alpha import reader

    with pytest.raises(reader.NotThisReader, match="CONTRACTION_RESCUE_ENABLED"):
        fired_one(_mark(ticker, as_of, resistance=324.73, support=290.49, events=[]),
                  [{}, {"CONTRACTION_RESCUE_ENABLED": True}], frame_loader=_loader(_frame(ticker, as_of)))


def test_the_concordance_chip_says_it_reads_the_old_reader_not_that_the_engine_failed(new_reader):
    from types import SimpleNamespace

    import domains.calibration.agreement as agreement_chip
    from domains.calibration.grading import grade_one

    ticker, as_of = MISSED
    mark = SimpleNamespace(id=1, verdict="box")
    chip = agreement_chip._compute(mark, lambda m: grade_one(
        _mark(ticker, as_of, resistance=324.73, support=290.49), [{}], frame_loader=_loader(_frame(ticker, as_of)))[0])
    assert chip["state"] == "untested" and chip["kind"] == "old_reader"
    assert "box-only read" in chip["detail"]


def test_the_engine_overlay_refuses_by_name_under_the_new_reader(new_reader, monkeypatch):
    import domains.calibration.frame_store as store
    from domains.calibration import router

    ticker, as_of = MISSED
    monkeypatch.setattr(store, "load_frame", _loader(_frame(ticker, as_of)))
    monkeypatch.setattr(router, "_ENGINE_READS", {})
    with pytest.raises(HTTPException) as refused:
        router.calibration_engine_read(ticker=ticker, as_of=as_of, frame_digest=None, db=None)
    assert refused.value.status_code == 409
    assert refused.value.detail["class"] == "old_reader_only"


def test_the_new_readers_record_refuses_the_old_reader_by_name():
    """The door's other half: the record is the new reader's, so it is never answered by the old one."""
    from engine_alpha import reader

    stamp: dict = {}
    with pytest.raises(reader.NotThisReader, match="read_box"):
        reader.read_record("T", None, stamp=stamp)
    assert stamp == {"reader": "old"}

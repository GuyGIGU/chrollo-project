"""The workbench says why a mark missed in the reader's own words.

Go-live plan, task 5. The workbench's "why did this mark miss" once read the OLD reader's box and its trace (the box
cascade's rejects); the reader carries its own trail (each step's stage and words) and its boxes, so the reason comes
from there, resolved in the backend (EC-28).

His own drawings, from the sealed fixture: NET to Tue 15/09/2026 (the reader reads lines and no LPS yet on his
day) and ALB to Mon 13/04/2026 (with one trading day deleted from the middle, the chart the reader refuses).
"""
from __future__ import annotations

import sys

import pandas as pd

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


def test_the_miss_shows_the_readers_box_and_its_reason_from_its_own_trail(monkeypatch):
    from engine_alpha import two_eyes
    from webapp.backend import frame_store

    ticker, as_of = MISSED
    frame = _frame(ticker, as_of)
    read = two_eyes.read(ticker, frame.loc[:pd.Timestamp(as_of)])
    box = next(s.saying for s in read.trail if s.stage == "box")
    lps = next(s.saying for s in read.trail if s.stage == "LPS")
    assert box.startswith("R 324.73") and "S 290.49" in box          # his box, as the reader drew it
    assert lps.startswith("no LPS")

    monkeypatch.setattr(frame_store, "load_frame", _loader(frame))
    chip = fired._chip_from_fired(_mark(ticker, as_of), {"fired": False, "fired_window": [as_of, as_of]})
    assert chip["state"] == "miss" and chip["kind"] == "missed"
    assert chip["stage"] == "lines, no LPS yet" == read.state
    assert box in chip["detail"] and lps in chip["detail"]
    assert chip["detail"].startswith("the new reader")


def test_a_chart_the_reader_refused_is_a_failed_read_never_no_box():
    ticker, as_of = REFUSED
    frame = _frame(ticker, as_of)
    holed = frame.drop(frame.index[len(frame) // 2])
    reason = fired._miss_reason(_mark(ticker, as_of), frame_loader=_loader(holed))
    assert reason["stage"] == "the read failed"
    assert "missing from the middle" in reason["detail"] and "box" not in reason["detail"]


def test_a_chart_the_universe_door_refused_is_not_scanned_never_no_box(monkeypatch):
    from engine_alpha import universe_door

    monkeypatch.setattr(universe_door, "apply_baseline_filters_with_reason",
                        lambda df: (None, ("sma200", "under its 200-day average")))
    ticker, as_of = MISSED
    reason = fired._miss_reason(_mark(ticker, as_of), frame_loader=_loader(_frame(ticker, as_of)))
    assert reason["stage"] == "not scanned"
    assert "never read" in reason["detail"] and "sma200" in reason["detail"]

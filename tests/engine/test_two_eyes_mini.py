"""Task 13 of the two-eyes reader: the mini — both boxes live, one setup.

His two sentences that are the task: *"if you are reffering to mini consolidations then both boxes live, they are a
part of the same setup"* (Sun 20/09/2026) and *"The Mini consolidation is always built with it's own rail set - the
LPS read can be against it if it is inside/near it/resting on it and the trigger is always read against the LPS by
itself"* (asked Sat 12/09/2026, answered Sun 13/09/2026). The yardstick is his drawings: the standard carries the
minis he stands behind today (`tests/regression/test_marks_corpus_drawing.py`, ``_MINI_CHARTS``), a BAND and a SPAN
each, no anchor days (the band's top is the span's first day's high, its bottom the span's last day's low), so "to
the cent" is no yardstick for a mini; the span and half the parent's range are.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest


def _iso(value) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


def _walk_on_his_last_day(setup: dict):
    """The walk on his drawing, read on his last receding day, as the reader runs it."""
    from engine_alpha.two_eyes import build_line, prepare, walk
    from engine_alpha.two_eyes import method_numbers as M
    from engine_alpha.two_eyes.frame import DAILY_RANGE
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration.yardstick import his_last_lps_day
    from tools.regression.marks_corpus import setup_key

    frames, _ = load_sealed_fixture()
    raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
    prepared = prepare(raw.loc[:pd.Timestamp(his_last_lps_day(setup))])
    line = build_line(prepared)
    far = line.far(M.FAR_VIEW_FLOOR_RANGES)
    ranges = prepared[DAILY_RANGE].to_numpy(dtype=float)
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    days = [d.date() for d in prepared.index]
    found = walk.elect(line.committed, [t for t in far if t.committed], ranges, high, low, days=days,
                       read_bar=len(prepared) - 1)
    return found, days, prepared


@pytest.fixture(scope="module")
def his_minis() -> list:
    """His drawings that carry a mini, each with the walk on his last receding day."""
    from tools.regression.marks_corpus import load_corpus, setup_key

    out = []
    for setup in load_corpus():
        if not setup.get("mini"):
            continue
        found, days, prepared = _walk_on_his_last_day(setup)
        out.append({"key": setup_key(setup), "setup": setup, "found": found, "days": days, "prepared": prepared})
    assert {m["setup"]["ticker"] for m in out} == {"DSGN", "MSGS"}     # the standard's own list, kept there
    return out


# --------------------------------------------------------------------------- #
# S1. The yardstick: the walk's own listing holds the mini pair he drew       #
# --------------------------------------------------------------------------- #
def _listed_near_his_mini(found, days, setup: dict) -> list:
    """The BORN pairs whose two lines each lie within half the parent's range of his band and whose two anchors
    fall inside his span."""
    band, span = setup["mini"]["band"], tuple(_iso(v) for v in setup["mini"]["span"])
    half = 0.5 * found.winner.unit
    return [p for p in found.pairs.values()
            if p.birth_bar is not None
            and abs(p.R - band["R"]) <= half and abs(p.S - band["S"]) <= half
            and span[0] <= days[p.opening_bar] <= span[1] and span[0] <= days[p.second_bar] <= span[1]]


def test_the_walk_lists_the_mini_pair_he_drew(his_minis):
    """The plan's first clause for task 13 (*"with YOUR parent lines injected, the same pair functions LIST the
    mini pair YOU DREW"*): on each drawing that carries a mini, the walk's own listing on his last receding day
    holds a pair that became a box, both lines within half the parent's range of his band, both anchors inside
    his span. DSGN: 10.97 / 9.82 (Tue 27/01 and Fri 30/01/2026), a box on Tue 17/02/2026. MSGS: 345.48 / 325.27
    (Wed 15/04 and Thu 16/04/2026), a box on Tue 05/05/2026 — the pair the reader shows as the parent."""
    for m in his_minis:
        found, days = m["found"], m["days"]
        assert found.winner is not None, m["key"]
        near = _listed_near_his_mini(found, days, m["setup"])
        assert near, f"{m['key']}: no born pair within half the parent's range of his mini {m['setup']['mini']}"
        if m["setup"]["ticker"] == "DSGN":
            assert any(days[p.birth_bar] == dt.date(2026, 2, 17) and abs(p.S - 9.82) < 0.005 for p in near)
        if m["setup"]["ticker"] == "MSGS":
            assert any(p.feet == found.winner.feet for p in near)      # his mini is the box the reader shows

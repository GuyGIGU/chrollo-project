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
    cut = raw.loc[:pd.Timestamp(his_last_lps_day(setup))]
    prepared = prepare(cut)
    line = build_line(prepared)
    far = line.far(M.FAR_VIEW_FLOOR_RANGES)
    ranges = prepared[DAILY_RANGE].to_numpy(dtype=float)
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    days = [d.date() for d in prepared.index]
    found = walk.elect(line.committed, [t for t in far if t.committed], ranges, high, low, days=days,
                       read_bar=len(prepared) - 1)
    return found, days, prepared, cut


@pytest.fixture(scope="module")
def his_minis() -> list:
    """His drawings that carry a mini, each with the walk on his last receding day."""
    from tools.regression.marks_corpus import load_corpus, setup_key

    out = []
    for setup in load_corpus():
        if not setup.get("mini"):
            continue
        found, days, prepared, cut = _walk_on_his_last_day(setup)
        out.append({"key": setup_key(setup), "setup": setup, "found": found, "days": days, "prepared": prepared,
                    "raw": cut})
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


# --------------------------------------------------------------------------- #
# S2. A place on the record for HOW the LPS sat against the mini              #
# --------------------------------------------------------------------------- #
def test_the_lps_record_carries_how_it_sat_against_the_mini():
    """His three positions (Sun 13/09/2026): *"the LPS read can be against it if it is inside/near it/resting on
    it"*. The record says WHICH box already (``read_against``); ``how`` says in, on or near, validated like a role,
    and is said only of the mini (OURS): the parent's read carries no word."""
    from engine_alpha.two_eyes import LPS_HOW, ROLE_MINI, ROLE_PARENT, Lps

    assert LPS_HOW == ("in", "on", "near")
    said = Lps(start_day=dt.date(2026, 3, 26), end_day=dt.date(2026, 3, 30), read_against=ROLE_MINI, trigger_price=10.70, how="in")
    assert said.how == "in"
    plain = Lps(start_day=dt.date(2026, 3, 26), end_day=dt.date(2026, 3, 30), read_against=ROLE_PARENT, trigger_price=10.70)
    assert plain.how is None
    with pytest.raises(ValueError):
        Lps(start_day=dt.date(2026, 3, 26), end_day=dt.date(2026, 3, 30), read_against=ROLE_MINI, trigger_price=10.70, how="inside")
    with pytest.raises(ValueError):
        Lps(start_day=dt.date(2026, 3, 26), end_day=dt.date(2026, 3, 30), read_against=ROLE_PARENT, trigger_price=10.70, how="in")


def test_the_lps_stage_stamps_the_box_and_the_word_it_is_handed(his_minis):
    """``lps.record`` stamps the role and the word the caller hands it; called as today it says the parent and no
    word, byte for byte (the LPS tests pin that). And the fire reads neither: the same pullback stamped as read
    against the mini, in, fires the same."""
    import dataclasses

    from engine_alpha.two_eyes import ROLE_MINI, ROLE_PARENT, lps, read as read_chart
    from engine_alpha.two_eyes.frame import DAILY_RANGE
    from engine_alpha.two_eyes import build_line

    m = next(x for x in his_minis if x["setup"]["ticker"] == "DSGN")
    prepared, found, days = m["prepared"], m["found"], m["days"]
    line = build_line(prepared)
    high, low = prepared["High"].to_numpy(dtype=float), prepared["Low"].to_numpy(dtype=float)
    ranges = prepared[DAILY_RANGE].to_numpy(dtype=float)
    won = found.winner
    pullback = lps.read(high, low, ranges, line.committed, R=won.R, S=won.S, box_unit=won.unit,
                        born_bar=won.birth_bar)
    plain, _, word = lps.record(pullback, days, read_bar=len(days) - 1)
    assert word == lps.FIRED and plain.read_against == ROLE_PARENT and plain.how is None
    stamped, steps, word2 = lps.record(pullback, days, read_bar=len(days) - 1, read_against=ROLE_MINI, how="in")
    assert word2 == word and stamped.read_against == ROLE_MINI and stamped.how == "in"
    assert (stamped.start_day, stamped.end_day, stamped.trigger_price) == (plain.start_day, plain.end_day,
                                                                             plain.trigger_price)
    assert "against the mini" in steps[0].saying and ", in" in steps[0].saying
    # The fire reads which box, the trigger and failure only: never the word.
    whole = read_chart("DSGN", m["raw"])
    assert whole.fired
    restamped = dataclasses.replace(whole, lps=dataclasses.replace(whole.lps, read_against=ROLE_MINI, how="near"))
    assert restamped.fired == whole.fired


# --------------------------------------------------------------------------- #
# S3. The mini stage, pure: which pairs may be a mini, and which one is        #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def his_40() -> dict:
    """Every drawing of his, the walk on his last receding day, keyed by the drawing (NGL has two)."""
    from tools.regression.marks_corpus import load_corpus, setup_key

    out = {}
    for setup in load_corpus():
        found, days, prepared, cut = _walk_on_his_last_day(setup)
        out[setup_key(setup)] = {"setup": setup, "found": found, "days": days, "prepared": prepared, "raw": cut,
                                "high": prepared["High"].to_numpy(dtype=float),
                                "low": prepared["Low"].to_numpy(dtype=float)}
    assert len(out) == 40
    return out


def _row(his_40: dict, ticker: str) -> dict:
    """The one drawing of a ticker (none of the tickers asked for here has two)."""
    rows = [r for k, r in his_40.items() if k.split(":")[0] == ticker]
    assert len(rows) == 1, ticker
    return rows[0]


def _find(row: dict):
    from engine_alpha.two_eyes import mini

    return mini.find(row["found"], row["high"], row["low"], len(row["days"]) - 1)


#: The charts of his 40 the stage draws a mini on, read on his last receding day, and the mini's two lines
#: (float32 on the record: compared with approx). A change is a named change.
_MINIS_ON_HIS_40 = {"DSGN": (10.97, 9.66), "EWTX": (31.29, 28.19), "RGR": (38.98, 37.47), "VIK": (86.90, 82.66),
                    "VLO": (265.61, 253.38)}


def test_on_dsgn_the_stage_names_the_mini_he_drew(his_40):
    """DSGN:2026-03-31, read Mon 30/03/2026: his mini 10.97 / 9.90 over Fri 23/01 to Tue 24/03/2026. The stage
    names 10.97 (Fri 23/01/2026) / 9.66 (Mon 26/01/2026), a box on Thu 12/02/2026: his top to the cent, his bottom
    within half his parent's range; a box with the role ``mini``, live, measured in its own frozen range."""
    from engine_alpha.two_eyes import ROLE_MINI, mini

    row = _row(his_40, "DSGN")
    history = _find(row)
    assert history, "no mini on DSGN"
    life = history[-1]
    days = row["days"]
    assert (life.pair.R, life.pair.S) == pytest.approx((10.97, 9.66), abs=0.005)
    assert days[life.pair.opening_bar] == dt.date(2026, 1, 23) and days[life.pair.s_bar] == dt.date(2026, 1, 26)
    assert days[life.pair.birth_bar] == dt.date(2026, 2, 12)
    band = row["setup"]["mini"]["band"]
    assert abs(life.pair.R - band["R"]) < 0.005 and abs(life.pair.S - band["S"]) <= 0.5 * row["found"].winner.unit
    box, step = mini.record(row["found"], history)
    assert box.role == ROLE_MINI and box.end_day is None and box.daily_range == pytest.approx(life.pair.unit)
    assert box.opened_day == dt.date(2026, 1, 23) and box.resistance.anchor_day == dt.date(2026, 1, 23)
    assert step.stage == "mini" and "10.97" in step.saying and "9.66" in step.saying


@pytest.mark.parametrize("ticker,why", [
    ("MSGS", "the box the reader shows IS his mini, and no pair inside it opened after its birth"),
    ("ANRO", "no pair inside the parent opened after its birth; his old twelve-day band was never a box"),
    ("ST", "the pair 35.41 / 33.77 — the mini he deleted on Sun 20/09/2026 — tops 0.67 ranges under the parent's "
           "resistance area: a small box inside, but not at the top"),
    ("ROIV", "29.64 / 28.67 is the parent's twin, both lines within the parent's own line areas"),
])
def test_the_stage_names_no_mini_where_he_drew_none(his_40, ticker, why):
    assert not _find(_row(his_40, ticker)), f"{ticker}: {why}"


def test_the_deleted_st_mini_is_a_small_box_inside_refused_only_at_the_top(his_40):
    """The ONE predicate that is ours and loudly so (layer 4: the top at or over the parent's resistance area):
    without it ST's deleted mini 35.41 / 33.77 would be named again, to the cent at the top."""
    from engine_alpha.two_eyes import mini

    row = _row(his_40, "ST")
    parent = row["found"].winner
    small = [p for p in row["found"].pairs.values() if p.birth_bar is not None and p.feet != parent.feet
             and mini.on_the_right_side(p, parent) and mini.inside_or_across(p, parent)
             and mini.a_small_box_inside(p, parent)]
    assert any((p.R, p.S) == pytest.approx((35.41, 33.77), abs=0.005) for p in small)
    assert not any(mini.at_the_top(p, parent) for p in small if (p.R, p.S) == pytest.approx((35.41, 33.77), abs=0.005))


#: The walk's own box 80 / 70 (its first fourteen points), then a rest at the top: the bars swing between 84 and
#: 76 for weeks, two ranges over the box's resistance and two under it, never back at the box's support.
_BOX_WITH_A_REST_AT_THE_TOP = [(0, 58), (1, 52), (2, 56), (3, 50), (5, 60), (6, 55), (8, 70), (9, 66), (11, 80),
                               (14, 70), (17, 79.5), (20, 70.6), (23, 78.8), (26, 70.4), (29, 84), (32, 76),
                               (35, 84), (38, 76), (41, 84), (44, 76), (47, 84), (50, 76), (53, 83.5), (56, 76.5)]


def test_a_rest_at_the_top_of_the_box_is_the_mini_on_a_hand_built_chart():
    """The box 80 / 70 (born on bar 25) keeps its place — the rest 84 / 76 lies across its resistance, never
    beyond it — and that rest is the mini: a small box inside the parent's right side, at the top, the first inner
    box to become one (bar 43), shown from that day with the parent still live."""
    from test_two_eyes_walk import _chart, _elect
    from engine_alpha.two_eyes import mini, walk

    chart = _chart(_BOX_WITH_A_REST_AT_THE_TOP)
    found = _elect(chart)
    assert (found.winner.R, found.winner.S) == (80.0, 70.0) and len(found.lives) == 1
    history = mini.find(found, chart["high"], chart["low"], chart["n"] - 1)
    assert history and (history[-1].pair.R, history[-1].pair.S) == (84.0, 76.0)
    assert history[-1].pair.birth_bar == 43 and history[-1].shown_bar == 43 and history[-1].why == walk.FIRST_BOX
    box, step = mini.record(found, history)
    assert box.role == "mini" and box.end_day is None and "84.00" in step.saying and "76.00" in step.saying


def test_the_boxs_own_legs_and_pokes_are_no_mini_on_the_walks_poke_chart():
    """The walk's poke specimen (`tests/engine/test_two_eyes_walk.py`): the box 80 / 70 and two pokes to 84 that
    come back. The first inner box to become one is 79.2 / 70.4 — the parent's twin, both lines within its own
    line areas — and nothing inside takes its place, so the chart carries no mini: the poke pair 84 / 72 is the
    box's own event, as the walk already says."""
    from test_two_eyes_walk import _BOX_WITH_POKES, _chart, _elect
    from engine_alpha.two_eyes import mini

    chart = _chart(_BOX_WITH_POKES)
    found = _elect(chart)
    assert (found.winner.R, found.winner.S) == (80.0, 70.0)
    inner = mini.candidates(found)
    assert any((p.R, p.S) == (84.0, 72.0) for p in inner)
    assert not mini.find(found, chart["high"], chart["low"], chart["n"] - 1)


def test_the_charts_of_his_40_with_a_mini_are_exactly_these(his_40):
    """The ratchet: on his last receding day the stage draws a mini on these five of his 40 and no other, each
    with these lines. Four of the five he never drew (his eye on the pictures decides, question 1 of the task);
    DSGN is his. Every candidate opened after the parent became a box (the parent's right side)."""
    from engine_alpha.two_eyes import mini

    named = {}
    for key, row in his_40.items():
        history = _find(row)
        if history:
            named[key.split(":")[0]] = (history[-1].pair.R, history[-1].pair.S)
        parent = row["found"].winner
        if parent is not None:
            assert all(p.opening_bar > parent.birth_bar for p in mini.candidates(row["found"]))
    assert set(named) == set(_MINIS_ON_HIS_40), sorted(named)
    for ticker, lines in _MINIS_ON_HIS_40.items():
        assert named[ticker] == pytest.approx(lines, abs=0.005), ticker


# --------------------------------------------------------------------------- #
# S4. The mini stage wired into the read, inside its own guard                #
# --------------------------------------------------------------------------- #
def _read_his(his_40: dict, ticker: str):
    from engine_alpha.two_eyes import read as read_chart

    row = _row(his_40, ticker)
    return row, read_chart(ticker, row["raw"])


def test_the_read_carries_the_mini_beside_the_parent(his_40):
    """DSGN through the one public way in, on his last receding day: the mini is on the record LAST in the boxes,
    after the walk's own (earlier..., parent); the parent, the LPS and the fire are byte for byte what they were;
    the trail says the mini after the box and before the LPS."""
    from engine_alpha.two_eyes import ROLE_MINI, ROLE_PARENT, walk

    row, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert read.lps.read_against == ROLE_PARENT and read.lps.how is None      # stage 6 reads the parent until S5
    assert read.mini is not None and read.mini.role == ROLE_MINI and read.boxes[-1] is read.mini
    assert (read.mini.resistance.price, read.mini.support.price) == pytest.approx((10.97, 9.66), abs=0.005)
    assert read.mini.opened_day == dt.date(2026, 1, 23) and read.mini.end_day is None
    walked, _, _ = walk.record(row["found"])
    assert read.boxes[:-1] == walked and read.parent == walked[-1]
    stages = [s.stage for s in read.trail]
    assert stages.index("mini") == stages.index("box") + 1 < stages.index("LPS")


def test_a_fault_in_the_mini_leaves_the_parent_only_read_standing(his_40, monkeypatch):
    """The guard is the inverse of the story's: by his ruling the LPS may be read against the mini, so a bug in
    the mini must never cost a fire — the read stands on the parent alone, with a step that says why, never
    `crashed`."""
    from engine_alpha.two_eyes import mini

    def falls_over(*args, **kwargs):
        raise RuntimeError("the mini stage fell over on purpose")

    monkeypatch.setattr(mini, "find", falls_over)
    row, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert read.mini is None and read.boxes[-1] == read.parent
    said = [s for s in read.trail if s.stage == "mini"]
    assert len(said) == 1 and "could not be read" in said[0].saying and "on purpose" in said[0].saying


def test_no_read_of_his_40_carries_the_minis_failure_step(his_40):
    from engine_alpha.two_eyes import read as read_chart

    for key, row in his_40.items():
        read = read_chart(key.split(":")[0], row["raw"])
        assert not any(s.stage == "mini" and "could not be read" in s.saying for s in read.trail), key
        assert read.mini is None or read.boxes[-1] is read.mini


def test_keep_listing_changes_words_only_with_a_mini(his_40):
    from engine_alpha.two_eyes import read as read_chart

    row = _row(his_40, "DSGN")
    plain, listed = read_chart("DSGN", row["raw"]), read_chart("DSGN", row["raw"], keep_listing=True)
    assert (plain.boxes, plain.lps, plain.state, plain.mini) == (listed.boxes, listed.lps, listed.state, listed.mini)
    assert [s for s in plain.trail if s.stage == "mini"] == [s for s in listed.trail if s.stage == "mini"]

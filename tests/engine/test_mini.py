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
from types import SimpleNamespace

import pandas as pd
import pytest


def _iso(value) -> dt.date:
    return dt.date.fromisoformat(str(value)[:10])


def _walk_on_his_last_day(setup: dict):
    """The walk on his drawing, read on his last receding day, as the reader runs it."""
    from engine_alpha.reader import build_line, prepare
    from engine_alpha.box import walk
    from engine_alpha import numbers as M
    from engine_alpha.chart import DAILY_RANGE
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration.board_helpers import his_last_lps_day
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


@pytest.fixture(autouse=True)
def _the_mini_stage_on(monkeypatch):
    """The stage is sunset (``MINI_ENABLED`` off since Fri 30/10/2026, his word) and kept whole behind its switch: this
    module pins the stage itself, so it reads with the switch ON. The one test of the sunset turns it off again."""
    from engine_alpha import numbers as M

    monkeypatch.setattr(M, "MINI_ENABLED", True)


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
    assert {m["setup"]["ticker"] for m in out} == {"DSGN"}     # the standard's own list, kept there (MSGS's mini went with his redraw of Sat 10/10/2026)
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
    his span. DSGN: 10.97 / 9.82 (Tue 27/01 and Fri 30/01/2026), a box on Tue 17/02/2026. MSGS's mini (345.48 /
    325.27, the pair the reader shows as the parent) went with his redraw of Sat 10/10/2026: those lines are his box now."""
    for m in his_minis:
        found, days = m["found"], m["days"]
        assert found.winner is not None, m["key"]
        near = _listed_near_his_mini(found, days, m["setup"])
        assert near, f"{m['key']}: no born pair within half the parent's range of his mini {m['setup']['mini']}"
        if m["setup"]["ticker"] == "DSGN":
            assert any(days[p.birth_bar] == dt.date(2026, 2, 17) and abs(p.S - 9.82) < 0.005 for p in near)


# --------------------------------------------------------------------------- #
# S2. A place on the record for HOW the LPS sat against the mini              #
# --------------------------------------------------------------------------- #
def test_the_lps_record_carries_how_it_sat_against_the_mini():
    """His three positions (Sun 13/09/2026): *"the LPS read can be against it if it is inside/near it/resting on
    it"*. The record says WHICH box already (``read_against``); ``how`` says in, on or near, validated like a role,
    and is said only of the mini (OURS): the parent's read carries no word."""
    from engine_alpha.reader import LPS_HOW, ROLE_MINI, ROLE_PARENT, Lps

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

    from engine_alpha.reader import ROLE_MINI, ROLE_PARENT, read as read_chart
    from engine_alpha import lps
    from engine_alpha.chart import DAILY_RANGE
    from engine_alpha.reader import build_line

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
    assert len(out) == 52
    return out


def _row(his_40: dict, ticker: str) -> dict:
    """The one drawing of a ticker (none of the tickers asked for here has two)."""
    rows = [r for k, r in his_40.items() if k.split(":")[0] == ticker]
    assert len(rows) == 1, ticker
    return rows[0]


def _find(row: dict):
    from engine_alpha.box import mini

    return mini.find(row["found"], row["high"], row["low"], len(row["days"]) - 1)


# The 2026-10-21 size rule removes EWTX/RGR/SYRE, replaces DSGN's oversized band,
# and lets smaller NGL January/ORMP pairs through. Keep NGL's two setups distinct.
@pytest.mark.parametrize('share,eligible', [(0.7999, True), (0.8, False), (1.0, False), (1.2, False)])
def test_candidate_height_boundary_is_strict_before_the_inner_walk(share, eligible):
    from engine_alpha.box import mini

    parent = SimpleNamespace(R=100, S=90, area=1, height=10, birth_bar=15, feet=(0, 1))
    pair = SimpleNamespace(R=95 + 10 * share, S=95, area=1, height=10 * share,
                           birth_bar=25, opening_bar=20, feet=(20, 21))
    found = SimpleNamespace(winner=parent, pairs={'inner': pair})
    assert bool(mini.candidates(found)) is eligible


_MINIS_ON_HIS_40 = {
    "ALB:2026-04-13": (173.00, 157.27), "DSGN:2026-03-31": (10.745, 9.82),
    "FOSL:2026-02-18": (3.88, 3.52), "NGL:2026-01-20": (9.80, 9.40),
    "NGL:2026-04-20": (11.94, 11.32), "ORMP:2026-04-13": (3.48, 3.27),
    "SILC:2026-04-13": (20.50, 18.83), "ST:2026-04-17": (35.41, 33.77),
    "VIK:2026-06-11": (86.90, 82.66), "VLO:2026-07-08": (265.61, 253.38),
    # His drawings since the seal of 40 (the standard of Fri 30/10/2026): on four the mini is the shelf he drew as
    # THE box (ANET, CLOV, DSGX, CBLL near it); on CLDT, OKTA and VTMX he drew none.
    "ANET:2026-10-02": (200.68, 187.89), "CBLL:2026-10-28": (25.63, 24.00), "CLDT:2026-10-09": (13.21, 12.79),
    "CLOV:2026-10-27": (4.68, 4.35), "DSGX:2026-10-08": (79.11, 75.31), "OKTA:2026-09-03": (153.68, 146.65),
    "VTMX:2026-10-02": (35.23, 33.47),
}
_LPS_AGAINST_THE_MINI_ON_HIS_40 = {
    "ALB:2026-04-13": "on", "DSGN:2026-03-31": "in", "FOSL:2026-02-18": "on",
    "NGL:2026-01-20": "on", "ORMP:2026-04-13": "on", "VIK:2026-06-11": "near",
    "VLO:2026-07-08": "in",
    "ANET:2026-10-02": "near", "CLDT:2026-10-09": "near", "CLOV:2026-10-27": "in", "DSGX:2026-10-08": "on",
}


def test_dsgn_excludes_the_oversized_mini_and_finds_a_smaller_one(his_40):
    """The old 10.97 / 9.66 band is parent-sized; the smaller 10.745 / 9.82 pair remains eligible."""
    from engine_alpha.reader import ROLE_MINI
    from engine_alpha.box import mini

    row = _row(his_40, "DSGN")
    history = _find(row)
    assert history, "no mini on DSGN"
    life = history[-1]
    days = row["days"]
    assert (life.pair.R, life.pair.S) == pytest.approx((10.745, 9.82), abs=0.005)
    assert days[life.pair.r_bar] == dt.date(2026, 2, 3) and days[life.pair.s_bar] == dt.date(2026, 1, 30)
    assert days[life.pair.birth_bar] == dt.date(2026, 2, 20)
    assert not any(abs(p.R - 10.97) < 0.005 and abs(p.S - 9.66) < 0.005
                   for p in mini.candidates(row["found"]))
    assert all(h.pair.height < 0.8 * row["found"].winner.height for h in history)
    box, step = mini.record(row["found"], history)
    assert box.role == ROLE_MINI and box.end_day is None and box.daily_range == pytest.approx(life.pair.unit)
    assert box.opened_day == dt.date(2026, 1, 30) and box.resistance.anchor_day == dt.date(2026, 2, 3)
    assert step.stage == "mini" and "9.82" in step.saying


@pytest.mark.parametrize("ticker,why", [
    ("MSGS", "the box the reader shows IS his mini, and no pair inside it opened after its birth"),
    ("ANRO", "no pair inside the parent opened after its birth; his old twelve-day band was never a box"),
    ("ROIV", "29.64 / 28.67 is the parent's twin, both lines within the parent's own line areas"),
])
def test_the_stage_names_no_mini_where_he_drew_none(his_40, ticker, why):
    assert not _find(_row(his_40, ticker)), f"{ticker}: {why}"


def test_the_deleted_st_mini_is_a_mini_by_its_structure(his_40):
    """His ruling (Sat 03/10/2026, on question 1): "we should gate mini consolidation by their structure its just a
    semi smaller base inside/in the vicinity of a bigger one" — not by where it sits in the parent. ST's pair
    35.41 / 33.77 (the mini he deleted on Mon 21/09/2026) is a small box inside the parent 36.14 / 33.95, its top
    0.67 ranges under the parent's resistance area: by structure it is the mini the walk's life shows."""
    from engine_alpha.reader import ROLE_MINI
    from engine_alpha.box import mini

    row = _row(his_40, "ST")
    history = _find(row)
    assert history, "no mini on ST"
    assert (history[-1].pair.R, history[-1].pair.S) == pytest.approx((35.41, 33.77), abs=0.005)
    box, step = mini.record(row["found"], history)
    assert box.role == ROLE_MINI and "35.41" in step.saying and "33.77" in step.saying


#: The walk's own box 80 / 70 (its first fourteen points), then a rest at the top: the bars swing between 84 and
#: 76 for weeks, two ranges over the box's resistance and two under it, never back at the box's support.
_BOX_WITH_A_REST_AT_THE_TOP = [(0, 58), (1, 52), (2, 56), (3, 50), (5, 60), (6, 55), (8, 70), (9, 66), (11, 80),
                               (14, 70), (17, 79.5), (20, 70.6), (23, 78.8), (26, 70.4), (29, 84), (32, 76),
                               (35, 84), (38, 76), (41, 84), (44, 76), (47, 84), (50, 76), (53, 83.5), (56, 76.5)]


def test_a_rest_exactly_eighty_percent_tall_is_not_a_mini():
    """The parent remains 80 / 70; the 84 / 76 rest is exactly 80% as tall."""
    from test_walk import _chart, _elect
    from engine_alpha.box import mini, walk

    chart = _chart(_BOX_WITH_A_REST_AT_THE_TOP)
    found = _elect(chart)
    assert (found.winner.R, found.winner.S) == (80.0, 70.0) and len(found.lives) == 1
    history = mini.find(found, chart["high"], chart["low"], chart["n"] - 1)
    assert not history, "84 / 76 is exactly 80% of the parent height and is excluded"


def test_an_oversized_poke_cannot_block_the_smaller_seventy_percent_rest():
    """The 84 / 72 pair is larger than the parent; 79 / 72 remains eligible."""
    from test_walk import _BOX_WITH_POKES, _chart, _elect
    from engine_alpha.box import mini

    chart = _chart(_BOX_WITH_POKES)
    found = _elect(chart)
    assert (found.winner.R, found.winner.S) == (80.0, 70.0)
    inner = mini.candidates(found)
    assert not any((p.R, p.S) == (84.0, 72.0) for p in inner)
    history = mini.find(found, chart["high"], chart["low"], chart["n"] - 1)
    assert (history[-1].pair.R, history[-1].pair.S) == (79.0, 72.0)


def test_the_charts_of_his_40_with_a_mini_are_exactly_these(his_40):
    """The ratchet: on his last receding day the stage draws a mini on these seventeen of his 52 and no other, each
    with these lines. DSGN is his to the cent at the top; ST is the mini he deleted, back by his ruling on the
    structure; the other nine he never drew (his eye on the pictures). Every candidate opened after the parent
    became a box (the parent's right side)."""
    from engine_alpha.box import mini

    named = {}
    for key, row in his_40.items():
        history = _find(row)
        if history:
            named[key] = (history[-1].pair.R, history[-1].pair.S)
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
    from engine_alpha.reader import read as read_chart

    row = _row(his_40, ticker)
    return row, read_chart(ticker, row["raw"])


def test_the_read_carries_the_mini_beside_the_parent(his_40):
    """DSGN through the one public way in, on his last receding day: the mini is on the record LAST in the boxes,
    after the walk's own (earlier..., parent); the parent, the LPS and the fire are byte for byte what they were;
    the trail says the mini after the box and before the LPS."""
    from engine_alpha.reader import ROLE_MINI, ROLE_PARENT
    from engine_alpha.box import walk

    row, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert read.lps.read_against == ROLE_MINI and read.lps.how == "in"       # stage 6 reads the mini (S5)
    assert read.mini is not None and read.mini.role == ROLE_MINI and read.boxes[-1] is read.mini
    assert (read.mini.resistance.price, read.mini.support.price) == pytest.approx((10.745, 9.82), abs=0.005)
    assert read.mini.opened_day == dt.date(2026, 1, 30) and read.mini.end_day is None
    walked, _, _ = walk.record(row["found"])
    assert read.boxes[:-1] == walked and read.parent == walked[-1]
    stages = [s.stage for s in read.trail]
    assert stages.index("mini") == stages.index("box") + 1 < stages.index("LPS")


def test_a_fault_in_the_mini_leaves_the_parent_only_read_standing(his_40, monkeypatch):
    """The guard is the inverse of the story's: by his ruling the LPS may be read against the mini, so a bug in
    the mini must never cost a fire — the read stands on the parent alone, with a step that says why, never
    `crashed`."""
    from engine_alpha.box import mini

    def falls_over(*args, **kwargs):
        raise RuntimeError("the mini stage fell over on purpose")

    monkeypatch.setattr(mini, "find", falls_over)
    row, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert read.mini is None and read.boxes[-1] == read.parent
    said = [s for s in read.trail if s.stage == "mini"]
    assert len(said) == 1 and "could not be read" in said[0].saying and "on purpose" in said[0].saying


def test_with_the_mini_switched_off_the_read_carries_no_mini_and_the_lps_reads_against_the_parent(his_40, monkeypatch):
    """His word of Fri 30/10/2026: *"for now i want you to sun set, mini consolidation detection"*. ``MINI_ENABLED``
    off: DSGN, whose LPS reads against the mini with it on, carries no mini box, no mini step, and its LPS is read
    against the parent with no word for how it sat; the parent and its lines are what they were. Nothing is deleted:
    the switch back is one line."""
    from engine_alpha import numbers as M
    from engine_alpha.reader import ROLE_MINI, ROLE_PARENT

    row, with_mini = _read_his(his_40, "DSGN")
    assert with_mini.mini is not None and with_mini.lps.read_against == ROLE_MINI
    monkeypatch.setattr(M, "MINI_ENABLED", False)
    row, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.mini is None and not any(b.role == ROLE_MINI for b in read.boxes)
    assert read.parent == with_mini.parent and read.boxes == with_mini.boxes[:-1]
    assert read.lps is not None and read.lps.read_against == ROLE_PARENT and read.lps.how is None
    assert not any(s.stage == "mini" for s in read.trail)


def test_no_read_of_his_40_carries_the_minis_failure_step(his_40):
    from engine_alpha.reader import read as read_chart

    for key, row in his_40.items():
        read = read_chart(key.split(":")[0], row["raw"])
        assert not any(s.stage == "mini" and "could not be read" in s.saying for s in read.trail), key
        assert read.mini is None or read.boxes[-1] is read.mini


def test_keep_listing_changes_words_only_with_a_mini(his_40):
    from engine_alpha.reader import read as read_chart

    row = _row(his_40, "DSGN")
    plain, listed = read_chart("DSGN", row["raw"]), read_chart("DSGN", row["raw"], keep_listing=True)
    assert (plain.boxes, plain.lps, plain.state, plain.mini) == (listed.boxes, listed.lps, listed.state, listed.mini)
    assert [s for s in plain.trail if s.stage == "mini"] == [s for s in listed.trail if s.stage == "mini"]


# --------------------------------------------------------------------------- #
# S5. The LPS against the mini, on his condition                              #
# --------------------------------------------------------------------------- #
def test_where_a_low_sits_against_the_mini_in_its_own_area():
    """His three positions, measured in the mini's own area (half its frozen range): inside the band and clear of
    both lines is ``in``; inside and within the area of a line is ``on`` (resting on it, a slight poke included);
    outside and within the area of a line is ``near``; anything else is away, and the parent is read."""
    from engine_alpha.box import mini

    class Band:
        R, S, area = 10.0, 8.0, 0.3

    assert mini.where(9.0, Band) == "in"
    assert mini.where(8.2, Band) == "on" and mini.where(9.8, Band) == "on"
    assert mini.where(7.8, Band) == "near" and mini.where(10.2, Band) == "near"
    assert mini.where(7.5, Band) == "away" and mini.where(10.5, Band) == "away"
    assert mini.lps_box(7.5, Band) == ("parent", None) and mini.lps_box(9.0, Band) == ("mini", "in")
    assert mini.lps_box(9.0, None) == ("parent", None)


def test_on_dsgn_the_lps_is_read_against_the_mini_in_it(his_40):
    """DSGN on his last receding day: the pullback of Thu 26/03 to Mon 30/03/2026, its low 10.30, sits inside the
    mini 10.97 / 9.66 clear of both lines: read against the mini, ``in``; the trigger is still 10.70, the high of
    Mon 30/03/2026; it fires; the LPS step names the mini and the word."""
    from engine_alpha.reader import ROLE_MINI

    row, read = _read_his(his_40, "DSGN")
    assert read.fired and read.lps.read_against == ROLE_MINI and read.lps.how == "in"
    assert read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert (read.lps.start_day, read.lps.end_day) == (dt.date(2026, 3, 26), dt.date(2026, 3, 30))
    step = next(s for s in read.trail if s.stage == "LPS")
    assert "against the mini" in step.saying and ", in" in step.saying


def test_a_mini_born_after_the_pullback_ended_falls_back_to_the_parent(his_40, monkeypatch):
    """A mini that became a box only after the pullback's last day cannot be the box the pullback receded
    inside: the parent's read stands, with a trail sentence; never "no LPS". On his last receding day the
    pullback ends on the read day itself, so the case is read on his buy day (Tue 31/03/2026), where the pullback
    of Thu 26/03 to Mon 30/03/2026 ended the day before and the day crossed its trigger."""
    import dataclasses

    from engine_alpha import lps
    from engine_alpha.box import mini
    from engine_alpha.reader import prepare, read as read_chart
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.regression.marks_corpus import setup_key

    row = _row(his_40, "DSGN")
    frames, _ = load_sealed_fixture()
    buy = fixture_frame(frames, setup_key(row["setup"]), "DSGN").loc[:pd.Timestamp("2026-03-31")]
    real = mini.find(row["found"], row["high"], row["low"], len(row["days"]) - 1)
    as_built = read_chart("DSGN", buy)
    assert as_built.state == lps.CROSSED and as_built.mini is not None
    read_bar = len(prepare(buy)) - 1          # the read's own window, not the long frame's length
    late_pair = dataclasses.replace(real[-1].pair, birth_bar=read_bar)
    late = (dataclasses.replace(real[-1], pair=late_pair),)
    monkeypatch.setattr(mini, "find", lambda *a, **k: late)
    read = read_chart("DSGN", buy)
    assert read.failed is False and read.state == lps.CROSSED and read.mini is not None
    said = [s.saying for s in read.trail if s.stage == "LPS"]
    assert any("the mini became a box only on" in s and "read against the parent" in s for s in said)


def test_a_fault_on_the_minis_side_of_the_lps_falls_back_to_the_parent(his_40, monkeypatch):
    from engine_alpha.reader import ROLE_PARENT
    from engine_alpha import lps

    calls = []
    real = lps.read

    def second_call_falls_over(*args, **kwargs):
        calls.append(kwargs.get("R"))
        if len(calls) == 2:
            raise RuntimeError("the mini side fell over on purpose")
        return real(*args, **kwargs)

    monkeypatch.setattr(lps, "read", second_call_falls_over)
    _, read = _read_his(his_40, "DSGN")
    assert len(calls) == 2 and read.failed is False
    assert read.fired and read.lps.read_against == ROLE_PARENT and read.lps.how is None
    assert any("on purpose" in s.saying for s in read.trail if s.stage == "LPS")


def test_a_fault_in_the_chooser_falls_back_to_the_parent(his_40, monkeypatch):
    """The verifier's find (verify-13, P2): the chooser (`mini.lps_box`, and `mini.where` through it) ran before
    the guard, so a fault there crashed the whole read and lost the parent's fire. It is a mini-side fault like
    any other: the parent's read stands, the mini stays on the record, the trail says why."""
    from engine_alpha.reader import ROLE_MINI, ROLE_PARENT
    from engine_alpha.box import mini

    def falls_over(low, band):
        raise RuntimeError("the chooser fell over on purpose")

    monkeypatch.setattr(mini, "lps_box", falls_over)
    _, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert read.lps.read_against == ROLE_PARENT and read.lps.how is None
    assert read.mini is not None and read.boxes[-1].role == ROLE_MINI          # the mini stage itself stood
    assert any("could not be read" in s.saying and "on purpose" in s.saying for s in read.trail if s.stage == "LPS")


def test_a_fault_in_the_minis_lps_record_falls_back_to_the_parents_record(his_40, monkeypatch):
    """The same find, the other side of the chooser: the record stamped for the mini raising must give the
    parent's record, not a crashed read. A fault in the parent's own record stays what it was before the mini
    (stage 6's own business, not guarded here)."""
    from engine_alpha.reader import ROLE_MINI, ROLE_PARENT
    from engine_alpha import lps

    real = lps.record

    def mini_side_falls_over(pullback, days, read_bar, **kwargs):
        if kwargs.get("read_against") == ROLE_MINI:
            raise RuntimeError("the record on the mini's side fell over on purpose")
        return real(pullback, days, read_bar, **kwargs)

    monkeypatch.setattr(lps, "record", mini_side_falls_over)
    _, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.lps.trigger_price == pytest.approx(10.70, abs=0.005)
    assert read.lps.read_against == ROLE_PARENT and read.lps.how is None
    assert any("could not be made" in s.saying and "on purpose" in s.saying for s in read.trail if s.stage == "LPS")


#: The junk chart on which the mini's read would RESCUE a pullback the parent's ceiling refuses: read against the
#: mini whenever one stands (his condition dropped), KWR gains two fire days. His condition is the rule.
_KWR_DAYS_AS_BUILT = ("2026-06-22", "2026-06-23", "2026-06-24")


def _junk_fire_days(ticker: str) -> tuple:
    from core.calibration.replay import fired_window_sessions
    from engine_alpha.reader import read as read_chart
    from tools.regression import negative_corpus

    frames, meta = negative_corpus._load_fixture()
    case = next(c for c in meta["cases"] if c.get("key", c["ticker"]) == ticker)
    raw = frames[case.get("key", case["ticker"])]
    sessions, _ = fired_window_sessions(raw, raw.index[-1], [])
    return tuple(str(ts.date()) for ts in sessions if read_chart(ticker, raw.loc[:ts]).fired)


def test_kwrs_oversized_mini_cannot_rescue_later_days_even_with_the_position_condition_relaxed(monkeypatch):
    """The height filter now excludes the pair that historically rescued two later KWR days."""
    from engine_alpha.box import mini

    assert _junk_fire_days("KWR") == _KWR_DAYS_AS_BUILT
    monkeypatch.setattr(mini, "lps_box", lambda low, band: ("parent", None) if band is None else
                        ("mini", mini.where(low, band) if mini.where(low, band) != mini.AWAY else mini.NEAR))
    assert _junk_fire_days("KWR") == _KWR_DAYS_AS_BUILT  # the oversized mini is no longer a candidate


def test_the_lps_names_the_mini_on_every_chart_of_his_40_that_has_one(his_40):
    """On his last receding day the LPS is read against the mini on exactly the eleven charts whose pullback's low
    sits in, on or near it, each as pinned; on the six other charts with a mini (NGL, SILC, ST; CBLL, OKTA and VTMX
    since Fri 30/10/2026) the low is away, and on the thirty-five without one, against the parent. Fires on his day
    are the LPS tests' business."""
    from engine_alpha.reader import ROLE_MINI, ROLE_PARENT, read as read_chart

    against = {}
    for key, row in his_40.items():
        read = read_chart(key.split(":")[0], row["raw"])
        if read.lps is not None:
            against[key] = (read.lps.read_against, read.lps.how)
    named = {t: how for t, (role, how) in against.items() if role == ROLE_MINI}
    assert named == _LPS_AGAINST_THE_MINI_ON_HIS_40, sorted(named.items())
    assert set(named) < set(_MINIS_ON_HIS_40) and set(_MINIS_ON_HIS_40) - set(named) == {
        "NGL:2026-04-20", "SILC:2026-04-13", "ST:2026-04-17", "CBLL:2026-10-28", "OKTA:2026-09-03", "VTMX:2026-10-02"}
    assert against["DSGN:2026-03-31"] == (ROLE_MINI, "in")
    assert all(how is None for role, how in against.values() if role == ROLE_PARENT)


# --------------------------------------------------------------------------- #
# S6. The archive tie, and his drawing through the door                        #
# --------------------------------------------------------------------------- #
_MINI_KEYS = ("r_price", "r_anchor_date", "s_price", "s_anchor_date", "opened_date", "end_date", "daily_range")


def test_dsgn_crosses_the_adapter_with_both_boxes_one_trigger(his_40):
    """The adapter already carries a second box under the archive family's own names (build task 6): with the
    mini on the record, DSGN's row says both pairs, the parent's lines as the setup's, one trigger, the LPS
    against the mini, and the mini flag 1 — with no adapter change."""
    from engine_alpha.result import to_result

    _, read = _read_his(his_40, "DSGN")
    row = to_result(read)
    assert (round(row["_R"], 2), round(row["_S"], 2)) == (10.31, 9.00) and row["_trigger_price"] == pytest.approx(10.70)
    assert row["_two_eyes_lps_read_against"] == "mini" and row["_two_eyes_has_mini"] == 1
    assert all(f"_two_eyes_mini_{k}" in row for k in _MINI_KEYS)
    assert (round(row["_two_eyes_mini_r_price"], 2), row["_two_eyes_mini_r_anchor_date"]) == (10.74, "2026-02-03")
    assert (round(row["_two_eyes_mini_s_price"], 2), row["_two_eyes_mini_s_anchor_date"]) == (9.82, "2026-01-30")
    assert row["_two_eyes_mini_opened_date"] == "2026-01-30" and row["_two_eyes_mini_end_date"] is None
    assert row["_two_eyes_parent_r_anchor_date"] == "2025-12-05"


def test_an_lps_read_against_a_mini_that_is_not_on_the_record_falls_back_to_the_parent(his_40, monkeypatch):
    """The tie deferred from build task 6: 'mini' is said only with a stored mini. Inside the read's guard, never
    a raise on the record or in the adapter (the door calls the adapter unguarded): a mini stage that put no box
    with the role mini on the record cannot have the LPS read against it — the parent's read stands, with a
    sentence, and the row says parent and no mini."""
    import dataclasses

    from engine_alpha.reader import ROLE_PARENT
    from engine_alpha.box import mini
    from engine_alpha.result import to_result

    real = mini.record

    def wrong_role(found, history):
        box, step = real(found, history)
        return dataclasses.replace(box, role=ROLE_PARENT), step

    monkeypatch.setattr(mini, "record", wrong_role)
    _, read = _read_his(his_40, "DSGN")
    assert read.failed is False and read.fired and read.mini is None
    assert read.lps.read_against == ROLE_PARENT and read.lps.how is None
    assert any("no mini box is on the record" in s.saying for s in read.trail if s.stage == "LPS")
    row = to_result(read)
    assert row["_two_eyes_lps_read_against"] == "parent" and row["_two_eyes_has_mini"] == 0


def test_dsgn_through_the_one_door_carries_the_mini():
    """DSGN on his last receding day through `gate.evaluate_ticker`: one row, the parent's lines, one trigger,
    the LPS against the mini, the mini's seven keys."""
    from engine_alpha import gate
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.regression.marks_corpus import load_corpus, setup_key

    setup = next(s for s in load_corpus() if s["ticker"] == "DSGN")
    frames, _ = load_sealed_fixture()
    raw = fixture_frame(frames, setup_key(setup), "DSGN")
    watch = {}
    row = gate.evaluate_ticker("DSGN", raw.loc[:pd.Timestamp("2026-03-30")], watch=watch)
    assert isinstance(row, dict)
    assert (round(row["_R"], 2), round(row["_S"], 2)) == (10.31, 9.00) and row["_trigger_price"] == pytest.approx(10.70)
    assert row["_two_eyes_lps_read_against"] == "mini" and row["_two_eyes_has_mini"] == 1
    assert (round(row["_two_eyes_mini_r_price"], 2), round(row["_two_eyes_mini_s_price"], 2)) == (10.74, 9.82)
    assert watch["state"] == "fired" and watch["read"].mini is not None

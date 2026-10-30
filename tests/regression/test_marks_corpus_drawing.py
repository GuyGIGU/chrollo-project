"""The test standard carries what he actually DREW, not just his two prices.

Task 2 of the two-eyes-reader build plan. His calibration DB has always stored
the box's first and last day, the day each rail was anchored on, which rail he
drew first, his trigger's price, and — on the charts where he drew one — the
mini consolidation's own band and dates. The graduation export
(``tools.calibration.guided_list_export``) wrote only the two rail PRICES and the LPS span,
so two questions the rewrite is judged on could not be scored honestly:

* "did the engine list HIS pair?" — a pair is two dated anchors, and matching a
  price picks the earliest bar that happens to touch it. Twelve of his marks
  carry more than one bar at a rail price, so the answer was decided by chance.
* "did the engine find HIS mini?" — the corpus carried no mini at all.

These assertions are about the FILE, not about any engine behaviour: they say
the standard still carries his drawing. The ratchet's verdicts are pinned by
``setup_digest``, which deliberately does NOT read these new fields — his anchor
day is what the ENGINE is scored against (the yardstick), not what a fire
verdict is about, so carrying them must not void a single pinned verdict.
"""
from __future__ import annotations

from _paths import REPO_ROOT
import datetime as dt
import json
import os

import pytest

from tools.regression import marks_corpus

_ROOT = str(REPO_ROOT)
_CORPUS = os.path.join(_ROOT, "docs", "marks", "guided_list_2026-07.json")

# The charts carrying a mini consolidation when the standard was last exported
# (Thu 01/10/2026, 20:35 local). It is a written-down expectation, not a live
# read: if he draws or deletes a mini, this list moves in the SAME change as the
# re-export, so a mini can never appear or vanish from the standard unremarked.
# History: an earlier read reported five (it named ANRO, which carries none);
# ST's mini was in the standard for one export and he deleted it the same
# evening, together with ST's spring test. ROIV's went on Thu 01/10/2026, when
# he redrew its box ("Sorry Roiv was wrong": support 27.92 for 27.12).
_MINI_CHARTS = {"DSGN"}   # MSGS's mini went with his redraw of Sat 10/10/2026

#: Removes a key, where None would SET it (a null trigger is a real value).
_DROP = object()


def _setups() -> list[dict]:
    with open(_CORPUS, "r", encoding="utf-8") as f:
        return json.load(f)["setups"]


def _iso(value, what: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise AssertionError(f"{what} is not an ISO date: {value!r}")


def test_every_drawing_carries_its_box_dates_and_anchors():
    """His box is a span with two dated anchors; the corpus must say so."""
    missing = []
    for s in _setups():
        for key in ("box", "anchors", "first_rail"):
            if key not in s:
                missing.append(f"{s['ticker']}:{s.get('setup')}.{key}")
    assert not missing, (
        "the test standard does not carry what he drew: " + ", ".join(missing[:8])
        + " — widen tools.calibration.guided_list_export (his DB already stores all of it)"
    )

    for s in _setups():
        what = f"{s['ticker']}:{s.get('setup')}"
        start, end = s["box"]
        assert _iso(start, f"{what}.box[0]") <= _iso(end, f"{what}.box[1]"), what
        r_day = _iso(s["anchors"]["R"], f"{what}.anchors.R")
        s_day = _iso(s["anchors"]["S"], f"{what}.anchors.S")
        assert s["first_rail"] in ("resistance", "support"), (
            f"{what}.first_rail is {s['first_rail']!r}")
        # The box opens on the earlier anchor and is never extended left
        # (his ruling, Sat 12/09/2026), so neither anchor may precede it.
        assert min(r_day, s_day) == _iso(start, f"{what}.box[0]"), (
            f"{what}: the box opens on {start}, but its earliest anchor is "
            f"{min(r_day, s_day)}")


def test_his_anchor_day_is_the_bar_that_carries_his_rail_price():
    """The anchor is a DAY he picked, and that day's bar carries the price.

    This is the assertion that makes "nothing is resolved by matching a price"
    checkable: twelve of his thirty-five marks have more than one bar at a rail
    price (BODI, DLX, FOSL, JAZZ, MATX, NGL, NOK, NTCT, ORMP, PBT, RGR, ST), so
    a price match picks the earliest of them and silently moves his anchor left.
    Resistance sits on its day's HIGH and support on its day's LOW — if that
    ever stops being true, the corpus and his drawing have come apart.

    Hermetic: reads the committed fixture, never his frame store.
    """
    frames, _ = marks_corpus._load_fixture()
    checked = 0
    for s in _setups():
        what = f"{s['ticker']}:{s.get('setup')}"
        df = marks_corpus.fixture_frame(frames, marks_corpus.setup_key(s), None)
        if df is None or df.empty:
            continue
        for rail, column in (("R", "High"), ("S", "Low")):
            day = s["anchors"][rail]
            bars = df[df.index.strftime("%Y-%m-%d") == day]
            assert len(bars) == 1, (
                f"{what}.anchors.{rail} is {day}, which is not one bar of his "
                f"frozen frame ({len(bars)} found)")
            drawn, on_the_bar = s["rails_drawn"][rail], float(bars[column].iloc[0])
            assert abs(drawn - on_the_bar) < 0.005, (
                f"{what}: he anchored {rail} on {day}, whose {column.lower()} is "
                f"{on_the_bar:.2f}, but the rail is drawn at {drawn:.2f}")
            checked += 1
    assert checked == 2 * len(_setups()), (
        f"only {checked} of {2 * len(_setups())} anchors were checked — a frame "
        "missing from the fixture makes this guard pass by doing nothing")


def test_the_trigger_carries_its_price_and_a_missing_buy_says_so():
    """His trigger is a day AND the price the engine must fire at.

    A mark may legitimately carry no buy: when he re-dated YPF's pullback window
    on Tue 15/09/2026 the trigger he had drawn fell inside the new window, and
    the rule that a trigger sits strictly after the last pullback bar cleared it.
    That is "no buy marked", and it must be carried as an explicit null rather
    than refused or quietly filled in.
    """
    for s in _setups():
        what = f"{s['ticker']}:{s.get('setup')}"
        assert "trigger" in s and "trigger_price" in s, f"{what} carries no trigger pair"
        if s["trigger"] is None:
            assert s["trigger_price"] is None, (
                f"{what} has no trigger day but carries a trigger price")
        else:
            _iso(s["trigger"], f"{what}.trigger")
            assert isinstance(s["trigger_price"], (int, float)) and s["trigger_price"] > 0, (
                f"{what}.trigger_price is {s['trigger_price']!r}")


def test_the_minis_he_drew_ride_the_standard():
    """His mini is a second box: its own two lines, with its own dates."""
    drawn = {s["ticker"] for s in _setups() if s.get("mini")}
    assert drawn == _MINI_CHARTS, (
        f"the standard carries minis for {sorted(drawn)}, his DB holds "
        f"{sorted(_MINI_CHARTS)}")
    for s in _setups():
        mini = s.get("mini")
        if not mini:
            continue
        what = f"{s['ticker']}:{s.get('setup')}"
        lo, hi = mini["band"]["S"], mini["band"]["R"]
        assert hi > lo > 0, f"{what}.mini.band is not an ordered pair: {mini['band']}"
        m_start, m_end = (_iso(v, f"{what}.mini.span") for v in mini["span"])
        assert m_start <= m_end, what
        # The mini lives inside its parent's life, on the right side of it.
        b_start, b_end = (_iso(v, f"{what}.box") for v in s["box"])
        assert b_start <= m_start and m_end <= b_end, (
            f"{what}: the mini {m_start}..{m_end} is not inside the box "
            f"{b_start}..{b_end}")
        # Where his drawn bottom sits against his rails is REPORTED, never
        # asserted: the standard records what he drew, and the rule that tells
        # a mini from a new box is the engine's, recorded in docs/decisions.md
        # (build task 13, Sat 03/10/2026). Until then this test refused any
        # mini whose bottom held above his resistance — and he has named that
        # shape twice ("a mini consolidation that rests on the resistance",
        # Sat 29/08/2026; a rest above R "evolves to be a mini consolidation",
        # Sun 13/09/2026), so our rule must never refuse his drawing. Measured
        # on the one he stands behind today (MSGS's mini went with his redraw of
        # Sat 10/10/2026): DSGN's bottom 9.90 sits 0.41 under his resistance
        # 10.31, above his support.
        R, S = s["rails_drawn"]["R"], s["rails_drawn"]["S"]
        where = ("inside his rails" if S < lo < R else
                 "above his resistance" if lo >= R else "under his support")
        print(f"{what}: the mini's bottom {lo:.2f} sits {where} ({S:.2f} .. {R:.2f}); "
              f"its top {hi:.2f} {'over' if hi > R else 'under'} his resistance")


@pytest.mark.parametrize("what,broken,says", [
    # Each case must red ONE refusal, so each refusal is individually pinned:
    # a check nothing watches is a check anyone can delete (EC-27 — a guard's
    # tests assert WHICH condition refused).
    ("box is not a pair", {"box": ["2026-03-20"], "anchors": _DROP},
     "must be a [start, end] pair"),
    ("box ends before it starts", {"box": ["2026-03-25", "2026-03-20"], "anchors": _DROP},
     "start after end"),
    ("box opens left of his earliest anchor",
     {"box": ["2026-03-01", "2026-04-30"],
      "anchors": {"R": "2026-03-20", "S": "2026-03-25"}},
     "never extended left"),
    ("a rail with no anchor day", {"anchors": {"R": "2026-03-20"}, "box": _DROP},
     "needs a day for each rail"),
    ("an anchor that is not a date",
     {"anchors": {"R": "the 20th", "S": "2026-03-25"}, "box": _DROP},
     "not an ISO date"),
    ("a rail he never drew first", {"first_rail": "left"}, "not one of"),
    ("a buy price with no buy day", {"trigger": None, "trigger_price": 44.79},
     "a day AND a price"),
    ("a buy day with no price", {"trigger": "2026-03-20", "trigger_price": None},
     "a day AND a price"),
    ("a negative buy price", {"trigger": "2026-03-20", "trigger_price": -1.0},
     "trigger_price is"),
    ("a mini with no dates", {"mini": {"band": {"R": 10.0, "S": 9.0}}},
     "needs a band and a span"),
    ("a mini with one line", {"mini": {"band": {"R": 10.0}, "span": ["2026-03-20", "2026-03-25"]}},
     "needs R and S"),
    ("a mini drawn upside down",
     {"mini": {"band": {"R": 9.0, "S": 10.0}, "span": ["2026-03-20", "2026-03-25"]}},
     "R above S"),
    ("a mini span that is not a pair",
     {"mini": {"band": {"R": 10.0, "S": 9.0}, "span": ["2026-03-20"]}},
     "must be a [start, end] pair"),
    ("a mini that ends before it starts",
     {"mini": {"band": {"R": 10.0, "S": 9.0}, "span": ["2026-03-25", "2026-03-20"]}},
     "start after end"),
    # His drawn events (task 12b): each kind is a LIST of spans, because he draws two on one chart.
    ("an SOS written as one span, not a list of spans", {"sos": ["2026-03-20", "2026-03-25"]},
     "must be a list of [first day, last day] spans"),
    ("an empty list of last suppers", {"last_supper": []},
     "carries no span"),
    ("a spring that ends before it starts", {"phase_c": [["2026-03-25", "2026-03-20"]]},
     "start after end"),
    ("spring tests out of order",
     {"spring_test": [["2026-04-01", "2026-04-02"], ["2026-03-01", "2026-03-02"]]},
     "in the order of their first day"),
])
def test_the_loader_refuses_a_malformed_drawing(what, broken, says):
    """A malformed drawing fails the load LOUDLY — never silently skipped.

    A skipped mark shrinks the acceptance set without anyone noticing, which is
    the failure EC-7 exists to prevent.
    """
    good = dict(_setups()[0])
    for key, value in broken.items():
        if value is _DROP:
            good.pop(key, None)
        else:
            good[key] = value
    with pytest.raises(ValueError) as err:
        marks_corpus.validate_setup(good, ctx="probe")
    assert says in str(err.value), (
        f"{what}: refused, but for the wrong reason — {err.value}")


def test_the_real_corpus_still_loads():
    """The refusals above must not refuse his own drawings."""
    assert len(marks_corpus.load_corpus()) == len(_setups())


def test_carrying_his_drawing_does_not_void_a_pinned_verdict():
    """The new fields are not part of the fire verdict's identity.

    ``setup_digest`` answers "is this pinned verdict about THIS drawing?", and a
    verdict is about the window the engine must fire in. Reading his anchor days
    into the digest would mark all 35 marks redrawn at once and drop every
    hand-written stage tag with them.
    """
    base = dict(_setups()[0])
    before = marks_corpus.setup_digest(base)
    for field, value in (
        ("box", ["2026-01-02", "2026-02-02"]),
        ("anchors", {"R": "2026-01-02", "S": "2026-01-03"}),
        ("first_rail", "support"),
        ("trigger_price", 999.0),
        ("mini", {"band": {"R": 2.0, "S": 1.0}, "span": ["2026-01-02", "2026-01-03"]}),
        ("sos", [["2026-01-02", "2026-01-05"]]),
        ("phase_c", [["2026-01-02", "2026-01-05"]]),
        ("spring_test", [["2026-01-02", "2026-01-05"]]),
        ("last_supper", [["2026-01-02", "2026-01-05"]]),
    ):
        moved = dict(base)
        moved[field] = value
        assert marks_corpus.setup_digest(moved) == before, (
            f"{field} entered the verdict digest — every pinned verdict would be "
            "voided at once")


# --------------------------------------------------------------------------- #
# His drawn events (task 12b, Fri 02/10/2026)                                 #
# --------------------------------------------------------------------------- #
#: What he had drawn beside the LPS and the mini when the standard was last exported (Fri 30/10/2026, his 52
#: drawings): the spans, and the setups that carry at least one. A written-down expectation, not a live read: when
#: he draws or deletes an event these move in the SAME change as the re-export. A drawn event is a kind and a
#: span of days and nothing else; a setup without one is not his "no".
_HIS_DRAWN_EVENTS = {"sos": (38, 37), "phase_c": (12, 12), "spring_test": (4, 4), "last_supper": (10, 10)}


def test_his_drawn_events_ride_the_standard():
    """His SOS, his springs (Phase C), his spring tests and his last suppers are in the standard, each a span of
    days, so a word rule can be held to HIS marked bars by a test (his rule of Sat 26/09/2026)."""
    setups = marks_corpus.load_corpus()
    assert set(marks_corpus.DRAWN_EVENT_KEYS) == set(_HIS_DRAWN_EVENTS)
    for kind, (spans, charts) in _HIS_DRAWN_EVENTS.items():
        carried = [s for s in setups if kind in s]
        assert (sum(len(s[kind]) for s in carried), len(carried)) == (spans, charts), kind
        for s in carried:
            days = [(_iso(a, kind), _iso(b, kind)) for a, b in s[kind]]
            assert all(a <= b for a, b in days) and days == sorted(days), (s["ticker"], kind)
    by = {marks_corpus.setup_key(s): s for s in setups}
    assert by["SYRE:2026-02-19"]["phase_c"] == [["2026-01-02", "2026-01-05"]]
    assert by["SYRE:2026-02-19"]["sos"] == [["2026-02-11", "2026-02-13"]]
    assert by["VIK:2026-06-11"]["sos"] == [["2026-05-21", "2026-05-28"]]
    assert by["VIK:2026-06-11"]["last_supper"] == [["2026-05-29", "2026-06-03"]]
    assert by["PBT:2026-05-11"]["sos"] == [["2026-05-01", "2026-05-05"]]
    # He draws two of a kind on one chart: two SOS on EWTX (BODI's two spring tests went with his redraw,
    # which carries no event at all).
    assert len(by["EWTX:2026-03-31"]["sos"]) == 2 and "spring_test" not in by["BODI:2026-04-21"]

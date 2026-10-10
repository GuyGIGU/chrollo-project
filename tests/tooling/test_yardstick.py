"""The yardstick: the first honest number on his own charts.

Task 3 of the two-eyes-reader build. Everything the rewrite claims later is
measured against this, so the measurements themselves are pinned here — on
hand-built cases whose right answer is worked out from HIS rules, never copied
from what the tool happens to print.

The headline is deliberately strict, because the number that flattered us for
three sessions was the loose one: "did the engine fire somewhere in a window
around his setup" is not the question. The question is whether the engine's
OWN two lines carry a fire on his last receding day, at his trigger.
"""
from __future__ import annotations
from _paths import REPO_ROOT

import datetime as dt
import json
import os

import pytest

_ROOT = str(REPO_ROOT)


def _d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


# --------------------------------------------------------------------------- #
# The two arms                                                                #
# --------------------------------------------------------------------------- #
def test_the_tool_names_exactly_the_switches_the_ledger_records():
    """The method arm is the 27 switches the ledger says carry the method.

    Drift here is silent and total: a switch left out of the arm means the
    "method" column measures something that is not the method, and every
    number under it is wrong in a way no other test would catch.
    """
    from tools.calibration import yardstick

    with open(os.path.join(_ROOT, "docs", "flag_ledger.md"), encoding="utf-8") as f:
        text = f.read()
    start = text.index("## The final-method switches")
    end = text.index("\n## ", start + 1)
    ledger = set()
    for line in text[start:end].splitlines():
        if line.startswith("| `") and line.count("|") >= 4:
            ledger.add(line.split("`")[1])

    assert len(ledger) == 27, f"the ledger's fate table lists {len(ledger)}, not 27"
    assert set(yardstick.METHOD_SWITCHES) == ledger


def test_the_two_arms_are_all_off_and_all_on():
    from tools.calibration import yardstick

    today = yardstick.arm_overrides(yardstick.ARM_TODAY)
    method = yardstick.arm_overrides(yardstick.ARM_METHOD)
    # Both old-engine arms also name the reader, off: since the flip the switch defaults on.
    assert set(today) == set(method) == set(yardstick.METHOD_SWITCHES) | {"TWO_EYES_READER_ENABLED"}
    assert today.pop("TWO_EYES_READER_ENABLED") is False and method.pop("TWO_EYES_READER_ENABLED") is False
    assert not any(today.values()), "today's engine is every method switch OFF"
    assert all(method.values()), "the method arm is every method switch ON"
    with pytest.raises(ValueError):
        yardstick.arm_overrides("neither")


def test_the_third_arm_is_the_new_reader_with_every_method_switch_off():
    from tools.calibration import yardstick

    assert yardstick.ARMS == (yardstick.ARM_TODAY, yardstick.ARM_METHOD, yardstick.ARM_NEW)
    new = yardstick.arm_overrides(yardstick.ARM_NEW)
    assert new.pop("TWO_EYES_READER_ENABLED") is True
    assert set(new) == set(yardstick.METHOD_SWITCHES), "every method switch is named"
    assert not any(new.values()), "the old method's switches are the old engine's: none is on beside the new reader"


def test_the_third_arm_reads_through_the_door_with_the_readers_own_lines_fire_or_no_fire():
    """The new reader is read as the scan would read it: the long frame cut at the day, the universe door before
    the read, and its own lines reported whether it fired or not."""
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, flag_capture, load_sealed_fixture
    from tools.calibration import yardstick

    setups = {setup_key(s): s for s in load_corpus()}
    frames, _ = load_sealed_fixture()

    def read(key, day):
        setup = setups[key]
        with flag_capture(**yardstick.arm_overrides(yardstick.ARM_NEW)):
            return yardstick._read_one_day(setup["ticker"], fixture_frame(frames, key, setup["ticker"]), _d(day))

    fired = read("SYRE:2026-02-19", "2026-02-17")               # his last receding day
    assert fired["fired"] and fired["error"] is None
    assert (round(fired["R"], 2), round(fired["S"], 2)) == (35.31, 32.26)
    assert fired["lps_end"] == _d("2026-02-17") and fired["trigger_price"] == pytest.approx(37.22)
    assert fired["box_start"] == _d("2025-12-11")
    assert yardstick.strict_hit(setups["SYRE:2026-02-19"], [fired])
    bought = read("SYRE:2026-02-19", "2026-02-18")              # his buy day: lines, and nothing on the board
    assert not bought["fired"] and bought["state"] == "crossed" and round(bought["R"], 2) == 35.31
    refused = read("JAZZ:2026-02-24", "2026-02-11")             # the universe door refuses his day
    assert refused["error"] == "no frame" and refused["R"] is None and not refused["fired"]
    assert yardstick.first_difference(setups["JAZZ:2026-02-24"], refused, 1.0) == "no frame"


# --------------------------------------------------------------------------- #
# The strict headline, and the chance column beside it                        #
# --------------------------------------------------------------------------- #
def _setup(**over) -> dict:
    """One drawn setup, in the corpus's own shape."""
    base = {
        "ticker": "TEST",
        "rails_drawn": {"R": 100.0, "S": 90.0},
        "lps": ["2026-03-02", "2026-03-06"],
        "trigger": "2026-03-09",
        "trigger_price": 101.5,
        "box": ["2026-01-05", "2026-03-06"],
        "anchors": {"R": "2026-01-06", "S": "2026-01-05"},
        "first_rail": "support",
    }
    base.update(over)
    return base


def _read(day: str, **over) -> dict:
    """One engine read of one chart on one day."""
    # `lps_end` is the day the ENGINE's own run of receding days ended. His
    # `trigger` is the day he would BUY — the next session. They are one day
    # apart on every one of his drawings, so they are never compared directly.
    base = {"day": _d(day), "fired": True, "R": 100.0, "S": 90.0,
            "box_start": _d("2026-01-05"), "lps_end": _d("2026-03-06"),
            "trigger_price": 101.5, "stage": None, "seconds": 0.01}
    base.update(over)
    return base


def test_his_last_receding_day_is_the_end_of_his_last_shelf():
    from tools.calibration import yardstick

    assert yardstick.his_last_lps_day(_setup()) == _d("2026-03-06")
    # A second shelf wins: it is the LAST run of receding days, not the first.
    two = _setup(lps2=["2026-03-10", "2026-03-13"])
    assert yardstick.his_last_lps_day(two) == _d("2026-03-13")


def test_the_strict_headline_needs_his_day_and_his_trigger():
    """Fired, on his last receding day, at his trigger — all three, or no hit."""
    from tools.calibration import yardstick

    setup = _setup()
    assert yardstick.strict_hit(setup, [_read("2026-03-06")]) is True

    # Right day, wrong trigger: the engine found a different buy.
    assert yardstick.strict_hit(
        setup, [_read("2026-03-06", trigger_price=104.0)]) is False
    # Right day, right price, but the engine's own run of receding days ended
    # somewhere else — it priced the same buy off a different bar.
    assert yardstick.strict_hit(
        setup, [_read("2026-03-06", lps_end=_d("2026-03-04"))]) is False
    # Read on his day and refused.
    assert yardstick.strict_hit(setup, [_read("2026-03-06", fired=False)]) is False
    # Fired, at his trigger — but a day late. This is the one the loose
    # headline used to count, and it is what the chance column is for.
    assert yardstick.strict_hit(setup, [_read("2026-03-09")]) is False
    # Never read on his day at all.
    assert yardstick.strict_hit(setup, [_read("2026-03-04")]) is False


def test_the_chance_column_shifts_his_day_and_his_trigger_with_it():
    """If his day had been a session later, his trigger would be THAT day's
    high — his own law. Sliding the day without sliding the trigger asks the
    headline's question twice, which is how the first version of this column
    agreed with the headline on every one of 70 reads."""
    from tools.calibration import yardstick

    setup = _setup()
    # 09/03 is three sessions after his day; its high is 103.0, so a fire that
    # day, ending its run that day, priced at 103.0, is the shifted hit.
    highs = {_d("2026-03-06"): 101.5, _d("2026-03-09"): 103.0}
    late = [_read("2026-03-09", lps_end=_d("2026-03-09"), trigger_price=103.0)]
    assert yardstick.chance_hit(setup, late, highs, shift=3) is True
    assert yardstick.chance_hit(setup, late, highs, shift=1) is False, \
        "three sessions away is not a chance hit inside one"
    # Priced off some other bar: not his buy on any day.
    assert yardstick.chance_hit(
        setup, [_read("2026-03-09", lps_end=_d("2026-03-09"), trigger_price=99.0)],
        highs, shift=3) is False
    # Fired that day, but its run of receding days ended somewhere else.
    assert yardstick.chance_hit(
        setup, [_read("2026-03-09", lps_end=_d("2026-03-04"), trigger_price=103.0)],
        highs, shift=3) is False


def test_a_setup_with_no_buy_can_never_be_a_strict_hit():
    """A drawing with no buy marked can never be scored a hit.

    All of them carry a buy today — YPF got its on Sun 20/09/2026, mid-build — but
    "no buy marked" is a legal state of a drawing, and the day it comes back
    nothing may quietly count it.
    """
    from tools.calibration import yardstick

    setup = _setup(trigger=None, trigger_price=None)
    reads = [_read("2026-03-06", lps_end=None, trigger_price=None)]
    assert yardstick.strict_hit(setup, reads) is False
    assert yardstick.chance_hit(setup, reads, {}, shift=3) is False


# --------------------------------------------------------------------------- #
# His lines, his opening day                                                  #
# --------------------------------------------------------------------------- #
def test_lines_are_close_when_both_sit_inside_half_a_daily_range():
    """His rail area is about half a daily range; that is the tolerance."""
    from tools.calibration import yardstick

    atr = 2.0          # half a daily range = 1.00
    assert yardstick.rails_close(100.0, 90.0, 100.9, 90.9, atr) is True
    assert yardstick.rails_close(100.0, 90.0, 101.1, 90.0, atr) is False, \
        "resistance 1.10 away is more than half a daily range"
    assert yardstick.rails_close(100.0, 90.0, 100.0, 88.9, atr) is False, \
        "support 1.10 away is more than half a daily range"
    assert yardstick.rails_close(100.0, 90.0, None, None, atr) is False
    with pytest.raises(ValueError):
        yardstick.rails_close(100.0, 90.0, 100.0, 90.0, 0.0)


def test_the_opening_day_is_counted_in_trading_days_and_keeps_its_sign():
    """Early and late are different failures; a magnitude hides which."""
    from tools.calibration import yardstick

    sessions = [_d(s) for s in ("2026-01-05", "2026-01-06", "2026-01-07",
                                "2026-01-08", "2026-01-09")]
    assert yardstick.open_day_delta(_d("2026-01-05"), _d("2026-01-08"), sessions) == 3
    assert yardstick.open_day_delta(_d("2026-01-08"), _d("2026-01-05"), sessions) == -3
    assert yardstick.open_day_delta(_d("2026-01-05"), _d("2026-01-05"), sessions) == 0
    assert yardstick.open_day_delta(_d("2026-01-05"), None, sessions) is None


def test_an_opening_that_moves_when_the_chart_is_reread_is_reported():
    """A shown line never moves, so neither does the day it opened.

    Read the same chart later and the box may grow to the right — but the day
    it opened is a fact about the past and must not move. When it does, the
    engine is re-anchoring the opening to whatever price just did.

    This is NOT his "openings running with the price", which is the
    anchor-polarity rule — an anchor may not start in the direction price is
    going — and is a test on the elected result that stage 10 must answer 0 of
    35. Two different measurements; they were briefly sharing a name here, and
    stage 10's acceptance will quote the other one.
    """
    from tools.calibration import yardstick

    steady = [_read("2026-03-04"), _read("2026-03-05"), _read("2026-03-06")]
    assert yardstick.opening_moved_on_reread(steady) is False

    moved = [_read("2026-03-04"),
             _read("2026-03-05", box_start=_d("2026-01-20")),
             _read("2026-03-06", box_start=_d("2026-01-20"))]
    assert yardstick.opening_moved_on_reread(moved) is True

    # A read that found no box at all is not evidence either way.
    assert yardstick.opening_moved_on_reread(
        [_read("2026-03-04"), _read("2026-03-05", box_start=None, fired=False)]) is False


def test_a_refused_frame_is_not_reported_as_wrong_lines():
    """On four of his drawings the universe door refuses his own last receding day,
    so the engine never sees a chart. Calling that "it drew the wrong lines"
    puts four charts in the board's biggest bucket accused of something they
    were never given the chance to do."""
    from tools.calibration import yardstick

    setup = _setup()
    refused = _read("2026-03-06", fired=False, R=None, S=None,
                    box_start=None, error="no frame")
    assert yardstick.first_difference(setup, refused, 2.0) == "no frame"
    crashed = _read("2026-03-06", fired=False, R=None, S=None,
                    box_start=None, error="ValueError: boom")
    assert yardstick.first_difference(setup, crashed, 2.0) == "the read crashed"


def test_the_json_dump_cannot_overwrite_a_sealed_file():
    """`--json docs/marks/guided_list_2026-07.json` would truncate his drawings
    in place, and a green run would say nothing. Every sibling instrument
    guards its dump; this one was shipped without the guard."""
    import inspect

    from tools.calibration import yardstick

    main_src = inspect.getsource(yardstick.main)
    json_at = main_src.index("args.json")
    guard_at = main_src.index("refuse_sealed_output(args.json)")
    assert guard_at < main_src.index('open(args.json, "w"'), \
        "the dump is opened before anything refuses a sealed path"
    assert json_at >= 0


# --------------------------------------------------------------------------- #
# Where the read leaves his drawing                                           #
# --------------------------------------------------------------------------- #
def test_the_first_difference_is_reported_in_the_order_he_reads():
    """He reads: lines, then the opening day, then the box's life, then the
    LPS, then the trigger. The FIRST of those to differ is the answer — a
    later one is downstream of it and tells him nothing."""
    from tools.calibration import yardstick

    setup = _setup()
    atr = 2.0
    assert yardstick.first_difference(setup, _read("2026-03-06"), atr) is None
    # Lines wrong AND trigger wrong: lines is the answer.
    both = _read("2026-03-06", R=110.0, trigger_price=104.0)
    assert yardstick.first_difference(setup, both, atr) == "lines"
    # Lines right, opening day wrong.
    assert yardstick.first_difference(
        setup, _read("2026-03-06", box_start=_d("2026-02-02")), atr) == "opening day"
    # Lines and opening right, no fire at all.
    assert yardstick.first_difference(
        setup, _read("2026-03-06", fired=False), atr) == "no fire"
    # Everything right but the buy.
    assert yardstick.first_difference(
        setup, _read("2026-03-06", trigger_price=104.0), atr) == "trigger"
    # The engine never read the chart.
    assert yardstick.first_difference(setup, None, atr) == "no read"


# --------------------------------------------------------------------------- #
# The junk, and the clock                                                     #
# --------------------------------------------------------------------------- #
def test_junk_is_ranked_worst_first():
    """He looks at the worst junk first; day order buries it."""
    from tools.calibration import yardstick

    fires = [{"key": "A", "day": "2026-01-02", "score": 41.0},
             {"key": "B", "day": "2026-01-01", "score": 72.5},
             {"key": "C", "day": "2026-01-03", "score": 55.0}]
    assert [f["key"] for f in yardstick.rank_junk(fires)] == ["B", "C", "A"]


def test_the_slowest_reads_keep_the_name_of_the_chart():
    """A sorted list of bare seconds cannot tell him WHICH chart is slow —
    the existing timing tool drops the name, which is why it was never used."""
    from tools.calibration import yardstick

    reads = {"AAA": 0.4, "BBB": 1.9, "CCC": 0.2, "DDD": 1.1, "EEE": 0.9, "FFF": 0.1}
    assert yardstick.slowest(reads, 3) == [("BBB", 1.9), ("DDD", 1.1), ("EEE", 0.9)]


# --------------------------------------------------------------------------- #
# The pages                                                                   #
# --------------------------------------------------------------------------- #
def test_the_pages_put_the_misses_first():
    """He wants to see what it got wrong, not scroll past what it got right."""
    from tools.calibration import yardstick

    rows = [{"key": "AAA", "strict": True}, {"key": "BBB", "strict": False},
            {"key": "CCC", "strict": True}, {"key": "DDD", "strict": False}]
    assert [r["key"] for r in yardstick.misses_first(rows)] == \
        ["BBB", "DDD", "AAA", "CCC"]


def test_the_page_draws_bars_and_never_candles():
    """His standing rule, and the one thing he checks in the first second."""
    import inspect

    from tools.calibration import yardstick

    source = inspect.getsource(yardstick)
    assert "candlestick" not in source.lower()
    # The bar drawer is the one the fidelity renderer already uses; a second
    # copy would drift from it.
    assert "_draw_bars" in source


# --------------------------------------------------------------------------- #
# His own numbers, which the later stages are scored against                  #
# --------------------------------------------------------------------------- #
_HIS_LINES = {
    # ticker: (resistance, support, the day he anchored resistance)
    "VIK": (87.00, 79.28, "2026-04-21"),
    "SYRE": (35.31, 32.26, "2025-12-11"),
    "ALB": (179.10, 160.02, "2026-01-15"),
    "FOSL": (4.00, 3.61, "2025-12-26"),
    "MSGS": (345.46, 320.70, "2026-02-18"),
    "ROIV": (30.33, 27.92, "2026-03-11"),     # redrawn by him on Thu 01/10/2026 (support was 27.12)
}


def test_his_buy_is_the_day_after_his_last_receding_day_priced_off_it():
    """The law the strict headline rests on, measured on every one of his marks.

    His BUY day is the very next trading day after his last run of receding
    days, and his trigger price is exactly the HIGH of that last receding day
    — every one, no exceptions (37 of 37 on Tue 29/09/2026). This is why his `trigger` field and the
    engine's LPS end are never compared to each other: they are one session
    apart by construction, and comparing them scores every setup a miss.

    If this ever stops holding, the strict headline is measuring something he
    did not draw, and this test is the only thing that would say so.
    """
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, load_sealed_fixture
    from tools.calibration.yardstick import his_last_lps_day

    setups = load_corpus()
    frames, _ = load_sealed_fixture()
    checked = 0
    for setup in setups:
        if setup.get("trigger") is None:
            continue
        raw = fixture_frame(frames, setup_key(setup), setup["ticker"])
        sessions = [d.date() for d in raw.index]
        last_receding = his_last_lps_day(setup)
        buy = _d(setup["trigger"])
        assert sessions.index(buy) - sessions.index(last_receding) == 1, (
            f"{setup_key(setup)}: his buy is not the session after his last "
            "receding day")
        high = float(raw.iloc[sessions.index(last_receding)]["High"])
        assert abs(high - float(setup["trigger_price"])) < 0.005, (
            f"{setup_key(setup)}: his trigger price is not that day's high")
        checked += 1
    assert checked == len(setups) >= 37, f"checked {checked} drawings of {len(setups)}"


#: The named charts, and the stage of the rewrite that has to turn each green.
#: They are RED today on purpose — this is the bar, written down before the
#: stage that must clear it exists, so it cannot be quietly lowered to fit.
#: `strict=True` means the day one of them starts passing, it FAILS until
#: somebody comes back here and removes the mark deliberately.
#: Two of them he has since blessed a SECOND reading of (Sun 20/09/2026, on the
#: first contact sheet; decisions record, same date), so passing this test is
#: sufficient for them but not necessary — the blessed alternative's exact
#: lines are settled with him at task 9's sitting, from pictures, and are
#: deliberately not invented here.
#: These pins read the METHOD arm, which is frozen: they record its misses and
#: can never turn green there. The stage that answers them is the new reader's
#: (stage 10 of the two-eyes reader), whose own pins for the same six charts
#: are in tests/engine/test_two_eyes_walk.py (VIK and SYRE read his pair to the
#: cent; ALB, FOSL, MSGS and ROIV are strict expected failures within half a
#: range of his). The converge of the build found this list naming the wrong
#: debtor (Fri 09/10/2026).
_STAGE_OF = {
    "VIK": "stage 10 — the election: the day the pair became a box",
    "SYRE": "stage 10 — the election: the day the pair became a box",
    "ALB": "stage 10 — the election order; he redrew it on Sun 20/09/2026 to the reading he "
           "called option 1 (the climax of the rise and its reaction, the clean chop from "
           "January kept); the shorter box he drew before is his option 2, acceptable",
    "FOSL": "stage 10 — the election order (one of the four it decides)",
    "MSGS": "stage 10 — the election order; he also blessed a shorter base "
            "that skips the dead space, so his marked box is not the only pass",
    "ROIV": "stage 10 — the election order (one of the four it decides)",
}


@pytest.fixture(scope="module")
def _engine_lines_on_his_day():
    """The method arm's own two lines, read on his last receding day."""
    from tools.regression.marks_corpus import load_corpus, setup_key
    from core.calibration.replay import fixture_frame, flag_capture, load_sealed_fixture
    from tools.calibration import yardstick

    setups = {s["ticker"]: s for s in load_corpus() if s["ticker"] in _STAGE_OF}
    frames, _ = load_sealed_fixture()
    out = {}
    with flag_capture(**yardstick.arm_overrides(yardstick.ARM_METHOD)):
        for ticker, setup in setups.items():
            raw = fixture_frame(frames, setup_key(setup), ticker)
            out[ticker] = yardstick._read_one_day(
                ticker, raw, yardstick.his_last_lps_day(setup))
    return out


@pytest.mark.parametrize("ticker", sorted(_STAGE_OF))
def test_the_named_charts_are_not_read_his_way_yet(ticker, _engine_lines_on_his_day):
    """Each of these is a chart where the engine must end up drawing HIS two
    lines. Today it does not, and the mark names the stage that owes it."""
    from tools.calibration import yardstick

    want_r, want_s, _ = _HIS_LINES[ticker]
    read = _engine_lines_on_his_day[ticker]
    got_r, got_s = read.get("R"), read.get("S")
    if got_r is not None and abs(got_r - want_r) < 0.005 and \
            abs(got_s - want_s) < 0.005:
        pytest.fail(
            f"{ticker} now reads as he drew it ({want_r}/{want_s}) — "
            f"{_STAGE_OF[ticker]} has landed. Remove {ticker} from _STAGE_OF "
            "and move its line into the board's kept ground.")
    pytest.xfail(f"{ticker}: the frozen method arm draws {got_r}/{got_s}, he drew "
                 f"{want_r}/{want_s} — answered by the new reader's {_STAGE_OF[ticker]} "
                 "(its own pin: tests/engine/test_two_eyes_walk.py)")


@pytest.mark.parametrize("ticker", sorted(_HIS_LINES))
def test_his_drawn_lines_are_what_the_named_charts_are_scored_against(ticker):
    """These numbers are HIS, read off his drawings, and every later stage's
    acceptance quotes them. If the corpus ever stops saying this, the stage
    tests are measuring something he did not draw."""
    with open(os.path.join(_ROOT, "docs", "marks", "guided_list_2026-07.json"),
              encoding="utf-8") as f:
        setups = json.load(f)["setups"]
    mark = next(s for s in setups if s["ticker"] == ticker)
    want_r, want_s, want_anchor = _HIS_LINES[ticker]
    assert round(mark["rails_drawn"]["R"], 2) == want_r
    assert round(mark["rails_drawn"]["S"], 2) == want_s
    assert mark["anchors"]["R"] == want_anchor

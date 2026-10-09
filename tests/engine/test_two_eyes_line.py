"""Stage 1 of the two-eyes reader: the swing line and the far view, causal by construction.

Task 8 of the two-eyes-reader build. The plan's Done-when, property by property, on every fixture frame
(his drawings — 35 when the task was built, 40 on Fri 02/10/2026 — the 37-ticker fleet, the 16 junk charts):

1. the far view is the fine line COLLAPSED: nested (every far turn is a fine turn), strictly alternating,
   each far turn with the day it became knowable, never earlier than the fine turn's;
2. cutting the frame on the right changes nothing already committed — the only things that may change are on
   a closed, named list (``line.FORMING_ONLY``);
3. trimming 20 days off the left changes nothing once the line has found its first turn again;
4. a missing number fails loud, by name;

and the unit rules: one rule for the order inside a bar, one bar may carry two turns, the line is built once
per read (the far views on demand, each once), every turn carries its size in daily ranges and its knowable day.
The floor of the far view is placed by the listing gate (task 9), so here it is a parameter, tried at the three
floors that gate will measure.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from engine_alpha.two_eyes import frame as frame_module
from engine_alpha.two_eyes import line as line_module
from engine_alpha import two_eyes_numbers as M
from engine_alpha.two_eyes.line import FORMING_ONLY, SwingLine, Turn, build

FAR_FLOORS = (1.5, 2.5, 3.0)       # the listing gate's three candidates (task 9)


# --------------------------------------------------------------------------- #
# The fixtures, prepared the way the reader prepares them                     #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def prepared_frames() -> dict:
    from tools.regression import negative_corpus, shadow_diff
    from core.calibration.replay import load_sealed_fixture

    frames = {}
    for name, loader in (("marks", load_sealed_fixture), ("fleet", shadow_diff._load_fixture),
                         ("junk", negative_corpus._load_fixture)):
        got, _ = loader()
        assert got, f"the {name} fixture went empty; every property here would pass vacuously"
        for key, raw in got.items():
            frames[f"{name}:{key}"] = frame_module.prepare(raw)
    assert len(frames) >= 80, f"only {len(frames)} fixture frames"
    return frames


def _key(t: Turn) -> tuple:
    return (t.bar, t.kind, t.price)


def _committed(turns) -> list:
    return [t for t in turns if t.knowable_bar is not None]


def _frame(highs, lows, start="2026-01-05", ranges=None) -> pd.DataFrame:
    """A bare prepared frame: OHLC plus the daily range column, one value per bar."""
    n = len(highs)
    df = pd.DataFrame({"Open": list(lows), "High": list(highs), "Low": list(lows), "Close": list(lows),
                       "Volume": [1000] * n}, index=pd.bdate_range(start, periods=n))
    df[frame_module.DAILY_RANGE] = 1.0 if ranges is None else list(ranges)
    return df


# --------------------------------------------------------------------------- #
# 1. The far view is the fine line collapsed                                  #
# --------------------------------------------------------------------------- #
def test_the_far_view_is_the_fine_line_collapsed(prepared_frames):
    folded_somewhere = False
    for name, df in prepared_frames.items():
        line = build(df)
        fine = {(t.bar, t.kind): t for t in line.turns}
        assert len(fine) == len(line.turns), f"{name}: the fine line repeats a turn"
        for floor in FAR_FLOORS:
            far = line.far(floor)
            assert len(far) >= 2, f"{name} at {floor}: a chart has at least its opening turn and the forming one"
            kinds = [t.kind for t in far]
            assert all(a != b for a, b in zip(kinds, kinds[1:])), f"{name} at {floor}: the far view must alternate"
            bars = [t.bar for t in far]
            assert bars == sorted(bars), f"{name} at {floor}: the far view is not in order"
            for t in far:
                fine_turn = fine.get((t.bar, t.kind))
                assert fine_turn is not None, f"{name} at {floor}: far turn {t} is not a turn of the fine line"
                assert fine_turn.price == t.price and fine_turn.day == t.day
                if t.knowable_bar is None:
                    assert t is far[-1], f"{name} at {floor}: only the last far turn may still be forming"
                else:
                    # The far view folds the fine line's COMMITTED turns, so a far turn is knowable no
                    # earlier than the fine turn it is, and never before its own bar.
                    assert fine_turn.knowable_bar is not None and t.knowable_bar >= fine_turn.knowable_bar, \
                        f"{name} at {floor}: a far turn became knowable before the fine turn it is"
                    assert t.knowable_bar >= t.bar, f"{name} at {floor}: a turn knowable before it printed"
                    assert t.knowable_day == df.index[t.knowable_bar].date()
            if len(far) < len(line.turns):
                folded_somewhere = True
    assert folded_somewhere, "no far view folded a single swing away — the property was never exercised"


def test_a_far_floor_under_the_lines_own_is_refused():
    line = build(_frame([10, 12, 11, 13, 12, 14], [9, 11, 10, 12, 11, 13]))
    with pytest.raises(ValueError):
        line.far(line.floor_ranges / 2)


# --------------------------------------------------------------------------- #
# 2. Cutting on the right changes nothing already committed                   #
# --------------------------------------------------------------------------- #
def _cuts(n: int) -> list:
    opening = [1, 2, 3, 5, 8]                       # before and around the line's opening
    late = list(range(max(1, n - 30), n - 1))
    early = list(range(60, max(60, n - 30), 40))
    return sorted(set(opening + early + late))


def _committed_by(turns, cut_bar: int) -> list:
    return [t for t in turns if t.knowable_bar is not None and t.knowable_bar <= cut_bar]


def test_cutting_the_frame_on_the_right_changes_nothing_already_committed(prepared_frames):
    compared = 0
    for name, df in prepared_frames.items():
        whole = build(df)
        far_whole = {floor: whole.far(floor) for floor in FAR_FLOORS}
        for cut in _cuts(len(df)):
            part = build(df.iloc[:cut + 1])
            expect = _committed_by(whole.turns, cut)
            got = _committed(part.turns)
            assert [t for t in got] == expect, (
                f"{name} cut at bar {cut}: the committed turns of the cut frame are not the whole frame's "
                f"turns knowable by then — the line looked ahead")
            # What the cut may change is on the closed list, and nothing else: after its committed turns the
            # cut line carries one forming turn — or, before the line has opened, two forming turns and no
            # committed one (the closed list's second item).
            tail = part.turns[len(got):]
            assert all(t.knowable_bar is None for t in tail), f"{name} cut at bar {cut}: a committed turn moved"
            assert len(tail) <= 1 or (len(tail) == 2 and not got), (
                f"{name} cut at bar {cut}: more than the forming turn differs; the closed list is {FORMING_ONLY}")
            for floor in FAR_FLOORS:
                got_far = _committed(part.far(floor))
                assert got_far == _committed_by(far_whole[floor], cut), \
                    f"{name} cut at bar {cut}, far view at {floor}: a far turn moved once later days were seen"
            compared += 1
    assert compared > 1000, compared


def test_the_closed_list_of_what_a_cut_may_change_is_named():
    assert FORMING_ONLY and all(isinstance(item, str) for item in FORMING_ONLY)
    assert any("forming" in item for item in FORMING_ONLY)


def test_the_readers_own_path_is_causal_too(prepared_frames):
    """Property 2 composed the way the reader runs it: the RAW frame cut on the right by a few days, then
    prepared (so the two-year window's left edge moves with the cut) and built. Aligned by day, every turn
    knowable by the cut day and past the stretch where the left edge is remembered (RESYNC_BARS after the
    shorter window opens) is the same turn on both; the far views likewise past their own stretch."""
    from tools.regression import shadow_diff
    from core.calibration.replay import load_sealed_fixture

    raws = {}
    for name, loader in (("marks", load_sealed_fixture), ("fleet", shadow_diff._load_fixture)):
        got, _ = loader()
        for key, raw in list(got.items())[:8]:
            raws[f"{name}:{key}"] = raw
    compared = 0
    for name, raw in raws.items():
        whole_df = frame_module.prepare(raw)
        whole = build(whole_df)
        for days in (1, 5, 20):
            part_df = frame_module.prepare(raw.iloc[:-days])
            part = build(part_df)
            cut_day = part_df.index[-1].date()
            # Settle from the LATER left edge (the whole frame's: its window starts later), so both lines have
            # had the full stretch to forget their own edge.
            settled = max(part_df.index[RESYNC_BARS], whole_df.index[RESYNC_BARS]).date()
            keep = lambda t, after: t.knowable_bar is not None and t.knowable_day <= cut_day and t.day >= after
            got = [(t.day, t.kind, t.price, t.knowable_day) for t in part.turns if keep(t, settled)]
            expect = [(t.day, t.kind, t.price, t.knowable_day) for t in whole.turns if keep(t, settled)]
            assert got == expect, f"{name} cut {days} day(s): the reader's own path moved a committed turn"
            assert got, f"{name} cut {days} day(s): nothing compared"
            for floor in FAR_FLOORS:
                far_settled = max(part_df.index[RESYNC_BARS_FAR[floor]], whole_df.index[RESYNC_BARS_FAR[floor]]).date()
                got_far = [(t.day, t.kind, t.price, t.knowable_day) for t in part.far(floor) if keep(t, far_settled)]
                expect_far = [(t.day, t.kind, t.price, t.knowable_day) for t in whole.far(floor) if keep(t, far_settled)]
                assert got_far == expect_far, f"{name} cut {days} day(s), far view at {floor}: a far turn moved"
            compared += 1
    assert compared >= 40, compared


# --------------------------------------------------------------------------- #
# 3. Trimming 20 days off the left changes nothing                            #
# --------------------------------------------------------------------------- #
def _shift(t: Turn, by: int) -> tuple:
    know = None if t.knowable_bar is None else t.knowable_bar + by
    return (t.bar + by, t.kind, t.price, know, t.size_ranges)


RESYNC_BARS = 40       # the fine line; measured worst on the 93 charts: 28 bars (fleet:TNC), median 1
#: The far views, floor by floor. The reader's own floor (1.5, placed by the listing gate) is held tightest: measured
#: worst 20 bars (marks:JAZZ, fleet:TNC). The two floors the gate tried and did not place need longer, the bigger
#: the floor: 69 bars at 2.5 (marks:ALB) and 94 at 3.0 (marks:SGHT, the day he drew it, Thu 01/10/2026; before it
#: 69, marks:ALB). Medians 4, 9 and 11.
RESYNC_BARS_FAR = {1.5: 40, 2.5: 80, 3.0: 110}


def _resync(trimmed_turns, whole_turns, by: int):
    """The first index of the trimmed line from which every later turn is the whole line's turn (the same
    bar, kind, price and knowable day; the size from the next turn on, since the first shared turn's leg
    starts in the trimmed line's own opening). None when the two never agree to the end."""
    whole = [(t.bar, t.kind, t.price, t.knowable_bar) for t in whole_turns]
    sizes = {(t.bar, t.kind): t.size_ranges for t in whole_turns}
    shifted = [(t.bar + by, t.kind, t.price, None if t.knowable_bar is None else t.knowable_bar + by)
               for t in trimmed_turns]
    for i, head in enumerate(shifted):
        if head in whole:
            j = whole.index(head)
            if whole[j:] == shifted[i:] and all(
                    sizes[(t.bar + by, t.kind)] == t.size_ranges for t in trimmed_turns[i + 1:]):
                return i
    return None


def test_trimming_20_days_off_the_left_changes_nothing(prepared_frames):
    """The trimmed line opens on its own first bars and reads them in its own direction; where every bar of
    a stretch covers the floor twice over, the two lines read those bars in opposite order until a narrower
    bar breaks the phase. Then they are the same line, turn for turn, to the end — and so is every far view,
    which needs longer the bigger its floor (its opening is decided from the new edge's own extremes).
    Measured on the 93 charts (Fri 02/10/2026): the fine line's worst stretch is 28 bars (fleet:TNC, median 1); the
    far views' 20, 69 and 94 bars at 1.5, 2.5 and 3.0 ranges (medians 4, 9 and 11). The bounds here carry a margin,
    and the floor the reader reads at is the one held tightest."""
    assert RESYNC_BARS_FAR[M.FAR_VIEW_FLOOR_RANGES] == min(RESYNC_BARS_FAR.values()) == RESYNC_BARS
    worst_bars = 0
    for name, df in prepared_frames.items():
        whole = build(df)
        trimmed = build(df.iloc[20:])
        k = _resync(trimmed.turns, whole.turns, 20)
        assert k is not None, f"{name}: the trimmed line never found the whole line again"
        bars_after_trim = trimmed.turns[k].bar
        assert bars_after_trim <= RESYNC_BARS, \
            f"{name}: the line depends on where its left edge falls for {bars_after_trim} bars"
        worst_bars = max(worst_bars, bars_after_trim)
        for floor in FAR_FLOORS:
            kk = _resync(trimmed.far(floor), whole.far(floor), 20)
            assert kk is not None, f"{name} at {floor}: the trimmed far view never found the whole one again"
            assert trimmed.far(floor)[kk].bar <= RESYNC_BARS_FAR[floor], \
                f"{name} at {floor}: the far view depends on where its left edge falls for " \
                f"{trimmed.far(floor)[kk].bar} bars"
    assert worst_bars > 0, "no chart needed a single bar to find the line again; the property was not exercised"


def test_the_unit_is_built_on_the_long_frame_before_the_cut():
    """The daily range of the first bars inside the window must be the long frame's, warmed up over the bars
    before the cut — not a fresh average that starts cold at the window's left edge."""
    from engine_alpha.two_eyes.daily_range import calculate_atr

    n = 900
    rng = np.random.default_rng(7)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    raw = pd.DataFrame({"Open": closes, "High": closes + 1.0 + rng.random(n), "Low": closes - 1.0 - rng.random(n),
                        "Close": closes, "Volume": 1000}, index=pd.bdate_range("2023-01-02", periods=n))
    prepared = frame_module.prepare(raw)
    assert len(prepared) < n, "the reading window is a cut"
    long_unit = calculate_atr(raw, M.DAILY_RANGE_DAYS).loc[prepared.index]
    cold_unit = calculate_atr(raw.loc[prepared.index], M.DAILY_RANGE_DAYS)
    pd.testing.assert_series_equal(prepared[frame_module.DAILY_RANGE], long_unit, check_names=False)
    assert not np.allclose(prepared[frame_module.DAILY_RANGE].iloc[:30], cold_unit.iloc[:30], equal_nan=True), \
        "the window's first bars carry a cold unit — the range was computed after the cut"
    assert np.isfinite(prepared[frame_module.DAILY_RANGE]).all(), "inside the window every bar has its range"


def test_the_reading_window_is_the_old_engines():
    from config import settings

    assert M.READ_WINDOW == settings.DAILY_STRUCTURE_PERIOD
    assert M.DAILY_RANGE_DAYS == 10


# --------------------------------------------------------------------------- #
# 4. A missing number fails loud                                              #
# --------------------------------------------------------------------------- #
def test_a_missing_high_fails_loud_by_day():
    df = _frame([10, 12, 11, 13, 12, 14], [9, 11, 10, 12, 11, 13])
    df.loc[df.index[3], "High"] = np.nan
    with pytest.raises(ValueError, match="2026-01-08"):
        build(df)


def test_a_missing_range_in_the_middle_fails_loud_and_the_warm_up_does_not():
    df = _frame([10, 12, 11, 13, 12, 14, 13, 15], [9, 11, 10, 12, 11, 13, 12, 14],
                ranges=[np.nan, np.nan, 1, 1, 1, 1, 1, 1])
    line = build(df)                                  # the first bars have no range yet: tolerated, named
    assert line.turns
    df.loc[df.index[5], frame_module.DAILY_RANGE] = np.nan
    with pytest.raises(ValueError, match="2026-01-12"):
        build(df)


def test_a_frame_without_the_range_column_is_refused():
    df = _frame([10, 12], [9, 11]).drop(columns=[frame_module.DAILY_RANGE])
    with pytest.raises(ValueError, match=frame_module.DAILY_RANGE):
        build(df)


# --------------------------------------------------------------------------- #
# The rules inside a bar, and what a turn carries                             #
# --------------------------------------------------------------------------- #
def test_one_rule_for_the_order_inside_a_bar():
    """The line comes into bar 3 rising; the bar tops at 20 and gives back the whole floor to 17 — so the bar
    carries the peak (the leg it was entered on ends) and then the valley (the new leg's extreme), in that
    order, and the peak is committed on that bar while the valley waits for a later bar."""
    line = build(_frame([10, 12, 14, 20, 18, 19.5, 21], [9, 11, 13, 17, 17.5, 18, 20]))
    on_bar_3 = [t for t in line.turns if t.bar == 3]
    assert [t.kind for t in on_bar_3] == ["peak", "valley"]
    peak, valley = on_bar_3
    assert peak.knowable_bar == 3 and valley.knowable_bar == 4, "one commit per bar; the valley commits later"
    assert peak.knowable_day == dt.date(2026, 1, 8) and valley.knowable_day == dt.date(2026, 1, 9)


def test_every_turn_carries_its_size_in_daily_ranges_and_its_knowable_day():
    ranges = [2.0, 2.0, 2.0, 4.0, 2.0, 2.0, 2.0]
    line = build(_frame([10, 12, 14, 20, 18, 19.5, 21], [9, 11, 13, 17, 17.5, 18, 20], ranges=ranges))
    opening = line.turns[0]
    assert opening.size_ranges is None, "the opening turn ends no leg"
    peak = next(t for t in line.turns if t.kind == "peak" and t.bar == 3)
    assert peak.size_ranges == pytest.approx((20 - 9) / 4.0), "the leg into the turn, in the range of the turn's own day"
    assert peak.day == dt.date(2026, 1, 8)
    forming = line.turns[-1]
    assert forming.knowable_bar is None and forming.knowable_day is None and not forming.committed
    assert all(t.committed for t in line.turns[:-1])


def test_the_line_is_built_once_per_read_and_each_far_view_once(monkeypatch):
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes import swing_line

    calls = []
    real = swing_line.turn_line

    def counting(highs, lows, floors):
        calls.append(len(highs))
        return real(highs, lows, floors)

    monkeypatch.setattr(swing_line, "turn_line", counting)
    df = _frame([10, 12, 11, 13, 12, 14, 13, 15], [9, 11, 10, 12, 11, 13, 12, 14])
    read = two_eyes.read("TEST", df.drop(columns=[frame_module.DAILY_RANGE]))
    assert read.failed is False
    assert len(calls) == 1, f"the read built the line {len(calls)} times"

    far_calls = []
    real_far = line_module._far_on_bars

    def counting_far(*args):
        far_calls.append(args[-1])
        return real_far(*args)

    monkeypatch.setattr(line_module, "_far_on_bars", counting_far)
    line = build(df)
    line.far(2.5)
    line.far(2.5)
    line.far(3.0)
    assert far_calls == [2.5, 3.0], "a far view is built once per floor and kept"


def test_the_stage_is_a_leaf_and_reads_no_setting():
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(line_module))
    named = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names] + \
            [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(m.startswith(("engine_alpha.structure", "engine_alpha.evaluation", "engine_alpha.scoring",
                                 "config")) for m in named), named
    assert isinstance(build(_frame([10, 12, 11], [9, 11, 10])), SwingLine)

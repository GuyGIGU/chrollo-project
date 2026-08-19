"""The seeding-refusal recorder at the anchor-collection seam (program
Task 9): None-default byte-identity, the seam's OWN closed vocabulary (never
the near-miss failing_leg set), and one producing case per leg (EC-22
discipline applied to a trace vocabulary).

Vocabulary narrowed 2026-08-17 (review, Beck): the advertised ``climax_age``
leg was proven UNREACHABLE — the AR sits after its climax, so a young climax
forces a young AR and ``ar_age`` always wins the leg choice — so the tuple
now holds exactly the three producible legs and the per-leg claim below is
TRUE. (The defensive scan-band guard also records ``frame_short`` when a
trace rides; it is settings-unreachable today — the 200-bar ROOT_TREND_SMA
gate refuses every frame short enough to land there — so it emits an
existing producible leg rather than advertising a new dead one.)"""
import numpy as np
import pandas as pd

from config import settings
from engine_alpha.structure.box_primitives import SEEDING_LEGS, collect_root_anchors


def _pole_frame(n=476):
    closes = np.empty(476)
    closes[:400] = 40 + 10 * np.arange(400) / 399
    closes[400:440] = 50 + 50 * np.arange(40) / 39
    closes[440:447] = np.linspace(98, 88.5, 7)
    shelf = np.arange(447, 465)
    closes[447:465] = np.where(shelf % 2 == 0, 90.0, 92.0)
    closes[465] = 103.0
    closes[466:] = 103.5
    idx = pd.bdate_range("2024-06-03", periods=476)
    df = pd.DataFrame({"Open": closes, "High": closes + 0.5,
                       "Low": closes - 0.5, "Close": closes,
                       "Volume": 200_000.0}, index=idx)
    return df.iloc[:n]


def test_vocabulary_is_its_own_closed_set():
    assert SEEDING_LEGS == ("frame_short", "below_trend_sma", "ar_age")
    from engine_alpha.structure.box_gates import GATE_LEGS
    assert not set(SEEDING_LEGS) & set(GATE_LEGS)   # never an overload


def test_none_default_is_byte_identical():
    df = _pole_frame()
    plain = collect_root_anchors(df, settings.MIN_BASE_DAYS)
    trace: list = []
    traced = collect_root_anchors(df, settings.MIN_BASE_DAYS,
                                  seeding_trace=trace)
    assert traced == plain                     # the walk's OUTPUT never moves


def test_young_ar_records_ar_age_with_pair_identity():
    # Truncated at bar 458 the AR (446) is 12 bars old on the 454-bar eval
    # frame — under the default 20-bar clock the pair is age-walled. The
    # trace names the pair; the anchors list stays silent about it.
    df = _pole_frame(n=459)
    trace: list = []
    anchors = collect_root_anchors(df, settings.MIN_BASE_DAYS,
                                   seeding_trace=trace)
    assert not any(a[2] == 446 for a in anchors)
    ar_recs = [r for r in trace if r["leg"] == "ar_age"]
    assert any(r["climax_bar"] == 439 and r["ar_bar"] == 446 for r in ar_recs)


def test_frame_short_and_below_trend_sma_record():
    short = _pole_frame().iloc[:30]
    trace: list = []
    assert collect_root_anchors(short, settings.MIN_BASE_DAYS,
                                seeding_trace=trace) == []
    assert [r["leg"] for r in trace] == ["frame_short"]

    closes = np.linspace(100, 40, 300)          # close under a falling SMA200
    idx = pd.bdate_range("2024-06-03", periods=300)
    down = pd.DataFrame({"Open": closes, "High": closes + 0.5,
                         "Low": closes - 0.5, "Close": closes,
                         "Volume": 200_000.0}, index=idx)
    trace = []
    assert collect_root_anchors(down, settings.MIN_BASE_DAYS,
                                seeding_trace=trace) == []
    assert [r["leg"] for r in trace] == ["below_trend_sma"]


def test_every_recorded_leg_is_in_the_vocabulary():
    for n in (459, 476):
        trace: list = []
        collect_root_anchors(_pole_frame(n=n), settings.MIN_BASE_DAYS,
                             seeding_trace=trace)
        assert all(r["leg"] in SEEDING_LEGS for r in trace)

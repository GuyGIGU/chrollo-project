"""The proven pieces arrive by COPY: each copy equals its original, pinned ONCE on the fixtures.

Task 7 of the two-eyes-reader build. Five pieces of the old engine are proven on his drawings — the daily
range, the swing line, the run reader, the box-end reader and the word rules — and the new reader must start
from them. It cannot IMPORT them: the new package is a leaf, and the rewrite must CHANGE these pieces (the
order inside one bar, his way of counting a turn, a box end no longer dated by a close), while the old copies
are pinned by tests that may not move before the flip. So they are copied, and the originals freeze.

This file is the proof that each copy started out identical: every piece, original against copy, on the SAME
inputs, compared record for record — not a hit count, which two different records can share. The daily range,
the line, its labels and the runs are compared over every sealed fixture frame (his 35 drawings, the 37-chart
fleet, the 16 junk cases); the rail count, the box end and the words over his 35 drawings, the only frames that
carry a box to read them against. The last pin runs each chain
whole (its own daily range, its own line, its own words) so the daily-range copy is exercised too, not just
handed an identical column.

It is pinned ONCE. The task that first changes a piece on purpose deletes that piece's pin in the same
commit, and every instrument that reports a number in that piece's terms moves to the copy that day.
"""
from __future__ import annotations
from _paths import REPO_ROOT

import datetime as dt
from types import SimpleNamespace

import numpy as np
import pandas as pd

# The originals, frozen. Imported HERE and in the frozen tests only: this file is the one place the two
# meet, because comparing them is its whole job.
from engine_alpha.structure.phases import climax as old_climax
from engine_alpha.structure.metrics import indicators as old_indicators
from engine_alpha.structure.events import market_structure as old_market_structure
from engine_alpha.structure.metrics import pivots as old_pivots


def _copies():
    """The new reader's copies, each imported only when a pin asks for it — so each piece's pin lands in the
    same commit as the piece it pins, and passes there."""
    import importlib

    class _Lazy:
        def __getattr__(self, name):
            return importlib.import_module(f"engine_alpha.two_eyes.{name}")

    return _Lazy()


def _all_fixture_frames():
    from tools.regression import negative_corpus, shadow_diff
    from core.calibration.replay import load_sealed_fixture

    frames = {}
    for name, loader in (("marks", load_sealed_fixture), ("fleet", shadow_diff._load_fixture),
                         ("junk", negative_corpus._load_fixture)):
        got, _ = loader()
        assert got, f"the {name} fixture went empty; every pin here would pass vacuously"
        for key, raw in got.items():
            frames[f"{name}:{key}"] = raw
    assert len(frames) >= 80, f"only {len(frames)} fixture frames"
    return frames


def _his_drawings():
    """His 35 drawings on their sealed frames, cut at his read day, as the inputs the box-end reader and
    the word rules take: his rails, his two anchor days and box start as frame positions, his last run of
    receding days with its lowest low."""
    import json
    import os

    from tools.regression.marks_corpus import setup_key
    from core.calibration.replay import load_sealed_fixture

    here = str(REPO_ROOT)
    with open(os.path.join(here, "docs", "marks", "guided_list_2026-07.json"), encoding="utf-8") as f:
        setups = json.load(f)["setups"]
    frames, _ = load_sealed_fixture()
    out = []
    for s in setups:
        raw = frames.get(setup_key(s))
        if raw is None:
            continue
        df = raw.loc[:pd.Timestamp(s["as_of"])]
        pos = {d.date(): i for i, d in enumerate(df.index)}

        def at(day):
            return pos.get(dt.date.fromisoformat(str(day)[:10]))

        start, r_anchor, s_anchor = at(s["box"][0]), at(s["anchors"]["R"]), at(s["anchors"]["S"])
        if None in (start, r_anchor, s_anchor):
            continue
        box = SimpleNamespace(start_bar=start, R=float(s["rails_drawn"]["R"]), S=float(s["rails_drawn"]["S"]),
                              r_anchor_bar=r_anchor, s_anchor_bar=s_anchor)
        lps = None
        window = s.get("lps2") or s.get("lps")
        if window and at(window[0]) is not None and at(window[1]) is not None:
            a, b = at(window[0]), at(window[1])
            lows = df["Low"].to_numpy(dtype=float)[a:b + 1]
            lps = SimpleNamespace(start_bar=a, low_bar=a + int(np.argmin(lows)), low=float(lows.min()))
        out.append((s["ticker"], df, box, lps))
    assert len(out) >= 33, f"only {len(out)} of his drawings could be placed on their frames"
    return out


def _with_atr(df, calculate_atr):
    out = df.copy()
    out["ATR_10"] = calculate_atr(out, 10)
    return out


def _unit(df):
    """The live engine's ONE scalar unit: ATR_10 six bars from the right (STRUCTURE_ATR_SAMPLE_OFFSET)."""
    return float(df["ATR_10"].iloc[-6])


def _line(module, df, unit):
    highs = df["High"].to_numpy(dtype=float)
    lows = df["Low"].to_numpy(dtype=float)
    return module.turn_line(highs, lows, module.turn_line_floors(df, unit))


# --------------------------------------------------------------------------- #
# Piece by piece, on identical inputs                                         #
# --------------------------------------------------------------------------- #
def test_the_daily_range_copy_is_bit_identical_on_every_fixture_frame():
    """Bit for bit, not within a tolerance: the recursion (Wilder's smoothing through lfilter) differs in
    the last bit from a re-typed loop on 8 of 35 frames, and the swing line's `>=` floor could flip on it."""
    c = _copies()
    for key, raw in _all_fixture_frames().items():
        for period in (10, 50):
            old = old_indicators.calculate_atr(raw, period).to_numpy()
            new = c.daily_range.calculate_atr(raw, period).to_numpy()
            assert np.array_equal(old, new, equal_nan=True), f"{key}: ATR_{period} differs"


def test_the_swing_line_labels_are_the_same_on_every_fixture_frame():
    c = _copies()
    for key, raw in _all_fixture_frames().items():
        df = _with_atr(raw, old_indicators.calculate_atr)
        zigzag = [(b, k, p) for (b, k, p, _) in _line(old_pivots, df, _unit(df))]
        assert old_market_structure.label_market_structure(zigzag) == \
            c.swing_line.label_market_structure(zigzag), f"{key}: the labels differ"


def test_turns_at_his_rails_are_counted_the_same():
    c = _copies()
    counted = 0
    for ticker, df, box, _ in _his_drawings():
        df = _with_atr(df, old_indicators.calculate_atr)
        unit = _unit(df)
        line = _line(old_pivots, df, unit)
        area = 0.5 * unit
        old = old_pivots.turns_at_rails(line, box.start_bar, box.R, box.S, area)
        assert old == c.swing_line.turns_at_rails(line, box.start_bar, box.R, box.S, area), ticker
        counted += any(old)
    assert counted > 0, "no drawing counted a turn at a rail; the pin would be vacuous"


def test_the_run_reader_copy_finds_the_same_runs_on_every_fixture_frame():
    c = _copies()
    runs_seen = 0
    for key, raw in _all_fixture_frames().items():
        df = _with_atr(raw, old_indicators.calculate_atr)
        line = _line(old_pivots, df, _unit(df))
        old = old_climax.runs_on_the_line(line)
        assert old == c.runs.runs_on_the_line(line), f"{key}: the runs differ"
        runs_seen += len(old)
    assert runs_seen > 0, "no fixture frame produced a run; the pin would be vacuous"


#: The word rules' copy was pinned equal to its original here, on his drawings, until build task 12b (Fri
#: 02/10/2026). That task changed the copy on purpose (the upthrust on his ALB word of Thu 01/10/2026), and the
#: two pins that compared the words (this one, and "each chain whole") left in the same commit, as the copy's own
#: header said they would. The copy's rules are now held by tests/engine/test_two_eyes_line_words.py (its copied
#: pure tests) and tests/engine/test_two_eyes_story.py (his own marked bars).


# --------------------------------------------------------------------------- #
# The chains, whole                                                           #
# --------------------------------------------------------------------------- #
def test_the_copies_numbers_start_at_the_values_the_originals_read():
    """Pinned once, like the pieces: each number the copies read from `method_numbers` starts at the value its
    original reads from the shared settings. The copied pure tests bracket some of them only loosely (the
    upthrust's poke could drift from 1.25 to 1.27 and pass them all); this fails on any drift. The task that
    first moves a number on purpose takes its name out of `pinned` in the same commit."""
    from config import settings
    from engine_alpha.two_eyes import method_numbers

    # Two left on purpose at build task 12b (Fri 02/10/2026): the ground of a push and the dig of a last supper
    # were re-placed in the box's own range, from his marks (tests/engine/test_two_eyes_story.py holds them now).
    pinned = ("LINE_WORD_AREA_ATR", "LINE_WORD_SUPPER_MAX_DAYS", "LINE_WORD_UPTHRUST_MIN_POKE_ATR",
              "TURN_LINE_FLOOR_ATR")
    assert set(pinned) <= {n for n in vars(method_numbers) if n.isupper()}
    for name in pinned:
        assert getattr(method_numbers, name) == getattr(settings, name), f"{name} left its original's value"

def test_a_changed_number_moves_the_version_stamp(monkeypatch):
    """The copies read their numbers from `method_numbers`, not from settings, and the version stamp hashed
    settings only: a tuned number would have changed the reading and kept the stamp, so the archived rows
    before and after could not be told apart. Each number, moved alone, must move the stamp."""
    from engine_alpha.freeze import manifest
    from engine_alpha.two_eyes import method_numbers

    names = sorted(n for n in vars(method_numbers) if n.isupper())
    assert len(names) == 16, names           # six from the copies (task 7; R15's margin left with the box-end copy at task 11), two from stage 1 (task 8), three from stages 2 and 3 (task 10), five from stage 6 (task 12a)
    before = manifest.manifest_hash()
    for name in names:
        value = getattr(method_numbers, name)
        moved = value + "x" if isinstance(value, str) else value + 1
        monkeypatch.setattr(method_numbers, name, moved)
        assert manifest.manifest_hash() != before, f"moving {name} left the version stamp where it was"
        monkeypatch.undo()
    assert manifest.manifest_hash() == before


def test_word_recall_feeds_the_old_election_the_old_engines_own_daily_range(monkeypatch):
    """Word recall's engine basis measures the OLD engine's election, so it is fed the daily range the old
    engine reads in the scan (the original's); his-rails basis reads the copies, so it is fed the copy's.
    Today the two ranges are bit-identical (pinned above). The day the copy changes on purpose, an engine
    basis fed the copy would report a different old engine with nobody having changed it."""
    from engine_alpha.two_eyes import daily_range
    from tools.calibration import word_recall
    from core.calibration.replay import load_sealed_fixture

    frames, _ = load_sealed_fixture()
    raw = next(iter(frames.values()))
    # Every bar's range is 1.0 in the COPY alone, wherever the copy's function has been imported to; the
    # original is untouched, so each basis shows which one it was fed.
    monkeypatch.setattr(daily_range, "_true_range", lambda df: np.ones(len(df)))
    his, old = word_recall._frames(raw)
    assert (his["ATR_10"] == 1.0).all(), "his-rails basis must read the copy's daily range"
    for period in (10, 50):
        pd.testing.assert_series_equal(old[f"ATR_{period}"], old_indicators.calculate_atr(raw, period),
                                       check_names=False)

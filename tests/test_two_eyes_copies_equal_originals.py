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

import datetime as dt
from types import SimpleNamespace

import numpy as np
import pandas as pd

# The originals, frozen. Imported HERE and in the frozen tests only: this file is the one place the two
# meet, because comparing them is its whole job.
from engine_alpha.structure import bricks as old_bricks
from engine_alpha.structure import climax as old_climax
from engine_alpha.structure import indicators as old_indicators
from engine_alpha.structure import line_words as old_words
from engine_alpha.structure import market_structure as old_market_structure
from engine_alpha.structure import pivots as old_pivots


def _copies():
    """The new reader's copies, each imported only when a pin asks for it — so each piece's pin lands in the
    same commit as the piece it pins, and passes there."""
    import importlib

    class _Lazy:
        def __getattr__(self, name):
            return importlib.import_module(f"engine_alpha.two_eyes.{name}")

    return _Lazy()


def _all_fixture_frames():
    from tools import negative_corpus, shadow_diff
    from tools.replay import load_sealed_fixture

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

    from tools.marks_corpus import setup_key
    from tools.replay import load_sealed_fixture

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def test_the_swing_line_copy_draws_the_same_line_on_every_fixture_frame():
    c = _copies()
    for key, raw in _all_fixture_frames().items():
        df = _with_atr(raw, old_indicators.calculate_atr)
        unit = _unit(df)
        assert _line(old_pivots, df, unit) == _line(c.swing_line, df, unit), f"{key}: the line differs"
        # and with the scalar unit alone, as the unit tests' bare frames run it
        bare = raw[["Open", "High", "Low", "Close"]]
        assert _line(old_pivots, bare, unit) == _line(c.swing_line, bare, unit), f"{key}: bare line differs"


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


def test_the_box_end_copy_reads_the_same_end_on_his_drawings():
    c = _copies()
    outcomes = set()
    for ticker, df, box, _ in _his_drawings():
        df = _with_atr(df, old_indicators.calculate_atr)
        atr = _unit(df)
        old = old_bricks.read_box_end(df, box, atr)
        new = c.box_end.read_box_end(df, box, atr)
        assert old == new, f"{ticker}: the box end differs"
        outcomes.add(None if old[0] is None else old[0]["kind"])
    assert len(outcomes) > 1, "every drawing ended the same way; the pin cannot tell rules apart"


def test_the_word_rules_copy_reads_the_same_words_on_his_drawings():
    c = _copies()
    named = minis = 0
    for ticker, df, box, lps in _his_drawings():
        df = _with_atr(df, old_indicators.calculate_atr)
        unit = _unit(df)
        # The mini rule reads only when handed an inner box, which his drawings do not carry: both sides get
        # the old engine's own, the one input the copy is not compared on.
        whole = SimpleNamespace(**vars(box), base_len=len(df) - box.start_bar, box_width=(box.R - box.S) / box.S)
        for inner in (None, old_bricks.find_inner_box(df, whole, unit)):
            old = old_words.read_line_words(df, box, unit, lps=lps, inner=inner)
            new = c.line_words.read_line_words(df, box, unit, lps=lps, inner=inner)
            assert old == new, f"{ticker}: the words differ"
            minis += old["mini"] is not None
        named += old["the_sos"] is not None
    assert named >= 20, f"THE SOS was named on only {named} drawings; the pin would be too thin"
    assert minis >= 1, "no drawing read a mini; the mini rule was never compared"


# --------------------------------------------------------------------------- #
# The chains, whole                                                           #
# --------------------------------------------------------------------------- #
def test_each_chain_whole_reads_the_same_on_his_drawings():
    """Each side stamps its OWN daily range, draws its OWN line and reads its OWN words and box end. The
    piece-by-piece pins hand both sides one column; only this one exercises the daily-range copy as the
    input the rest actually consume."""
    c = _copies()
    for ticker, raw_df, box, lps in _his_drawings():
        old_df = _with_atr(raw_df, old_indicators.calculate_atr)
        new_df = _with_atr(raw_df, c.daily_range.calculate_atr)
        old_unit, new_unit = _unit(old_df), _unit(new_df)
        assert old_unit == new_unit, ticker
        old_line, new_line = _line(old_pivots, old_df, old_unit), _line(c.swing_line, new_df, new_unit)
        assert old_line == new_line, ticker
        assert old_climax.runs_on_the_line(old_line) == c.runs.runs_on_the_line(new_line), ticker
        assert old_bricks.read_box_end(old_df, box, old_unit) == \
            c.box_end.read_box_end(new_df, box, new_unit), ticker
        assert old_words.read_line_words(old_df, box, old_unit, lps=lps) == \
            c.line_words.read_line_words(new_df, box, new_unit, lps=lps), ticker


def test_word_recall_measures_the_copies_and_reaches_the_old_engine_only_through_the_door():
    """The instrument that reports his words (THE SOS 23 of 25, Phase C 10 of 10 on his rails, measured on
    Mon 21/09/2026: identical to the original, all 130 of its rows) reads the new reader's copies from task 7
    on, so it is the one that will say when they first read differently. The block that measures the OLD
    engine's election asks the door. No piece of the old chart reader is imported directly."""
    import ast
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "tools", "word_recall.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    named = []
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module:
            named += [n.module] + [f"{n.module}.{a.name}" for a in n.names]
        elif isinstance(n, ast.Import):
            named += [a.name for a in n.names]
    old = [m for m in named if m.startswith(("engine_alpha.structure", "engine_alpha.evaluation",
                                             "engine_alpha.scoring"))
           or m == "engine_alpha.structure"]
    assert not old, f"word_recall imports the old chart reader: {old}"
    assert "engine_alpha.two_eyes.line_words" in named or "engine_alpha.two_eyes" in named



def test_the_copies_numbers_start_at_the_values_the_originals_read():
    """Pinned once, like the pieces: each number the copies read from `method_numbers` starts at the value its
    original reads from the shared settings. The copied pure tests bracket some of them only loosely (the
    upthrust's poke could drift from 1.25 to 1.27 and pass them all); this fails on any drift. The task that
    first moves a number on purpose takes its name out of `pinned` in the same commit."""
    from config import settings
    from engine_alpha.two_eyes import method_numbers

    pinned = ("BOX_END_BREAKOUT_ATR", "LINE_WORD_AREA_ATR", "LINE_WORD_SOS_MIN_GROUND_ATR",
              "LINE_WORD_SUPPER_DIG_ATR", "LINE_WORD_SUPPER_MAX_DAYS", "LINE_WORD_UPTHRUST_MIN_POKE_ATR",
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
    assert len(names) == 7, names
    before = manifest.manifest_hash()
    for name in names:
        monkeypatch.setattr(method_numbers, name, getattr(method_numbers, name) + 1)
        assert manifest.manifest_hash() != before, f"moving {name} left the version stamp where it was"
        monkeypatch.undo()
    assert manifest.manifest_hash() == before


def test_word_recall_feeds_the_old_election_the_old_engines_own_daily_range(monkeypatch):
    """Word recall's engine basis measures the OLD engine's election, so it is fed the daily range the old
    engine reads in the scan (the original's); his-rails basis reads the copies, so it is fed the copy's.
    Today the two ranges are bit-identical (pinned above). The day the copy changes on purpose, an engine
    basis fed the copy would report a different old engine with nobody having changed it."""
    from engine_alpha.two_eyes import daily_range
    from tools import word_recall
    from tools.replay import load_sealed_fixture

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

"""The adapter: the new reader's record, spoken in the old engine's shape.

Task 5 of the two-eyes-reader build. The new reader answers a `Read`; the
archive row, the wire, the board and the screen all speak the old result dict.
The adapter is the ONE place those two meet, so that when stages 1 to 7 fill
the record in, nothing downstream changes shape again.

The adapter is deliberately NOT part of the leaf package: it is the only file
allowed to know both vocabularies.
"""
from __future__ import annotations

from _paths import REPO_ROOT
import datetime as dt

import pandas as pd
import pytest


def _frame(n: int = 5) -> pd.DataFrame:
    days = pd.bdate_range("2026-03-02", periods=n)
    return pd.DataFrame(
        {"Open": [1.0] * n, "High": [2.0] * n, "Low": [0.5] * n,
         "Close": [1.5] * n, "Volume": [1000] * n}, index=days)


def _read_with_lines():
    from engine_alpha.two_eyes import record

    day = dt.date(2026, 1, 5)
    box = record.Box(resistance=record.Line(100.0, day),
                     support=record.Line(90.0, day),
                     opened_day=day, daily_range=2.0)
    lps = record.Lps(dt.date(2026, 3, 2), dt.date(2026, 3, 6),
                     record.ROLE_PARENT, trigger_price=101.5)
    return record.Read(ticker="TEST", as_of=dt.date(2026, 3, 6),
                       boxes=(box,), lps=lps, state="fired")


def test_no_lines_is_not_a_fire():
    """The skeleton answers "no lines" for every chart, and the scan must drop
    it exactly as it drops any structural reject — None, never a row."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes_adapter import to_result

    read = two_eyes.read("TEST", _frame())
    assert to_result(read) is None


def test_a_crashed_read_becomes_the_counted_failure_sentinel():
    """Not None. A refusal and a crash are both "no row", and the night has to
    be able to tell them apart — that distinction is why the sentinel exists.
    """
    from engine_alpha.evaluation import EVAL_ERROR
    from engine_alpha.two_eyes import record
    from engine_alpha.two_eyes_adapter import to_result

    crashed = record.crashed("TEST", dt.date(2026, 3, 6), "a high under its low")
    assert to_result(crashed) is EVAL_ERROR


def test_a_fire_is_whole_in_the_keys_its_readers_index_by_hand():
    """A fire row is whole or it is not a row.

    Downstream reads these with square brackets, so a missing one is a
    KeyError in the middle of a night's write, not a None in a column.
    """
    from engine_alpha.two_eyes_adapter import REQUIRED_KEYS, to_result

    result = to_result(_read_with_lines())
    assert isinstance(result, dict)
    missing = [k for k in REQUIRED_KEYS if k not in result]
    assert not missing, f"a fire row is missing {missing}"


def test_a_fire_says_its_base_window_so_the_sector_read_is_not_quietly_void():
    """The keys nobody would miss.

    The archive's sector-RS enrichment reads the base window with `.get()`, so
    leaving these out raises nothing at all and simply empties the column. A
    blind check found them absent. Its other two inputs are the base's first
    and last close, which this record does not carry yet — so RS stays empty
    for now, but for a stated reason rather than a missing key.
    """
    from engine_alpha.two_eyes_adapter import SILENTLY_LOST_KEYS, to_result

    result = to_result(_read_with_lines())
    for key in SILENTLY_LOST_KEYS:
        assert key in result, f"{key} is absent, and nothing downstream says so"
    assert result["_base_date_start"] == "2026-01-05"
    assert result["_base_date_end"] == "2026-03-06"


def test_the_forced_whole_numbers_are_whole_when_measured_and_empty_when_not():
    """Several archive columns are ints by contract; a float there is stored
    and then compared against an int forever after.

    And what this reader does not measure yet is EMPTY, never 0. The first
    version sent zeros for touches, breach days and the bar anchors, and the
    archive stored them as if they had been counted — a zero is
    indistinguishable from a measured zero forever after.
    """
    from engine_alpha.two_eyes_adapter import WHOLE_NUMBER_KEYS, to_result

    result = to_result(_read_with_lines())
    # None of them is measured yet. Base Len and LPS Length count trading
    # BARS on every old-reader row; a first version filled them with calendar
    # days, a second meaning in the same column. Stage 5 fills them, whole.
    for key in WHOLE_NUMBER_KEYS:
        assert result[key] is None, \
            f"{key} is {result[key]!r}: this reader does not measure it yet"


def test_the_setup_price_is_the_read_days_close_not_a_line():
    """The forward-returns backfill scales every trigger by the stored price.
    The resistance line stood in for it once, which would have regraded the
    outcome of every fire by the gap between the line and the close."""
    import dataclasses

    from engine_alpha.two_eyes_adapter import to_result

    read = dataclasses.replace(_read_with_lines(), close=95.37)
    assert to_result(read)["Current Price"] == 95.37


def test_every_two_eyes_fact_the_adapter_carries_is_a_column_the_archive_reads():
    """Drift in the other direction from the end-to-end archive test: a name
    the adapter invents that no archive column reads is a fact silently
    dropped on the floor at write time. The first version did exactly that
    with four of them."""
    from engine_alpha.two_eyes_adapter import to_result
    from engine_alpha.two_eyes_archive import TWO_EYES_COLUMN_SQL

    carried = [k for k in to_result(_read_with_lines()) if k.startswith("_two_eyes_")]
    assert carried, "the adapter carries none of the new reader's own facts"
    unread = [k for k in carried if k[1:] not in TWO_EYES_COLUMN_SQL]
    assert not unread, f"no archive column reads {unread}"


def test_the_two_lines_and_their_days_survive_the_crossing():
    from engine_alpha.two_eyes_adapter import to_result

    result = to_result(_read_with_lines())
    assert result["_R"] == 100.0 and result["_S"] == 90.0
    assert result["_trigger_price"] == 101.5
    assert result["_phase_b_start_date"] == "2026-01-05"
    assert result["_lps_zone_end_date"] == "2026-03-06"


def test_the_state_word_crosses_without_the_old_engine_rewording_it():
    """The screen's vocabulary is the operator's, and the adapter may not
    invent a word that is not in it."""
    from engine_alpha import two_eyes
    from engine_alpha.two_eyes_adapter import STATE_WORDS, to_state

    assert to_state(two_eyes.read("TEST", _frame())) == "no lines"
    assert "no lines" in STATE_WORDS, "his own table owns that word"

    from engine_alpha.two_eyes import record
    crashed = record.crashed("TEST", None, "boom")
    assert to_state(crashed) != "no lines", \
        "a read that fell over may not borrow the words for a chart that has none"
    assert to_state(crashed) not in STATE_WORDS, (
        "and its word is deliberately NOT on his ten-word table — the "
        "publisher raises on an unknown word, so a crashed read leaves as the "
        "counted-failure sentinel before a word is ever asked for")

    # An invented word never crosses, even from a future stage.
    with pytest.raises(ValueError):
        to_state(record.Read(ticker="TEST", state="looks promising"))


def test_the_adapter_is_not_part_of_the_leaf():
    """It is the one file allowed to know both vocabularies — which is exactly
    why it lives outside the package the leaf guard protects."""
    import os

    root = str(REPO_ROOT)
    assert os.path.exists(os.path.join(root, "engine_alpha", "two_eyes_adapter.py"))
    assert not os.path.exists(
        os.path.join(root, "engine_alpha", "two_eyes", "two_eyes_adapter.py"))


# --------------------------------------------------------------------------- #
# The switch, and the version stamp                                           #
# --------------------------------------------------------------------------- #
def test_the_switch_exists_and_is_off():
    """Every flip is his. It ships off, and the ledger carries its row."""
    from config import settings

    assert settings.TWO_EYES_READER_ENABLED is False


def test_the_ruleset_string_is_hand_bumped_and_in_the_manifest():
    """The engine's version stamp hashes the listed settings, their NAMES and
    the scoring registry — but NO reader code. Without a hand-bumped string,
    two different builds of the new reader stamp the same version, and an
    archive row cannot say which reader wrote it.
    """
    from config import settings
    from engine_alpha.freeze import manifest

    assert isinstance(settings.TWO_EYES_RULESET, str)
    assert settings.TWO_EYES_RULESET.strip()
    listed = manifest.manifest_inputs() if hasattr(manifest, "manifest_inputs") else None
    source = listed if listed is not None else open(manifest.__file__, encoding="utf-8").read()
    assert "TWO_EYES_RULESET" in str(source)
    assert "TWO_EYES_READER_ENABLED" in str(source)


def test_bumping_the_ruleset_string_moves_the_version_stamp(monkeypatch):
    """The whole point of the string: two builds of the new reader must not
    stamp the same version."""
    from config import settings
    from engine_alpha.freeze.manifest import manifest_hash

    before = manifest_hash()
    monkeypatch.setattr(settings, "TWO_EYES_RULESET", "two-eyes-0.0.0-probe")
    assert manifest_hash() != before


def test_the_flag_ledger_carries_the_new_switch():
    """EC-8: a new engine flag ships with the full protocol in ONE change."""
    import os

    root = str(REPO_ROOT)
    with open(os.path.join(root, "docs", "flag_ledger.md"), encoding="utf-8") as f:
        ledger = f.read()
    assert "TWO_EYES_READER_ENABLED" in ledger


# --------------------------------------------------------------------------- #
# The door                                                                    #
# --------------------------------------------------------------------------- #
def test_the_door_sends_the_read_to_the_new_reader_when_the_switch_is_on(monkeypatch):
    """One switch, one door, and the new reader answers every caller."""
    from config import settings
    from engine_alpha import reader

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)
    assert reader.which_reader() == reader.READER_NEW
    stamp: dict = {}
    out = reader.evaluate_ticker("TEST", _frame(), 0.0, None, stamp=stamp)
    assert out is None, "the skeleton reads no lines, so nothing fires"
    assert stamp == {"reader": "new"}


def test_every_way_through_the_door_answers_with_the_reader_it_stamps(monkeypatch):
    """The failure this whole door exists to prevent.

    A blind check found the switch reaching only ONE of the door's four ways
    in: `run_eval_chain` and `read_box` stamped "new" and then called the old
    engine anyway, so the chart-state page, the seed, the calibration
    workbench and the replay seam would all have read with the old engine
    while the stamp said otherwise. A stamp that names a reader which did not
    answer is worse than no stamp at all.
    """
    from config import settings
    from engine_alpha import reader

    from engine_alpha import evaluation
    from engine_alpha.structure.narrative import reader as narrative

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)

    # The discriminator. Comparing ANSWERS cannot tell the two readers apart
    # here — a short frame is refused by the old engine too, so both say None,
    # and the first version of this test passed against a deliberately broken
    # door. The old engine is made to explode instead: if any path still
    # reaches it, the test says so by name.
    def never(*a, **k):
        raise AssertionError("the OLD engine answered while the stamp said new")

    monkeypatch.setattr(evaluation, "_evaluate_ticker", never)
    monkeypatch.setattr(evaluation, "_run_eval_chain", never)
    monkeypatch.setattr(evaluation, "_run_guarded_chain", never)
    monkeypatch.setattr(narrative, "read_structure", never)

    frame = _frame()
    stamp: dict = {}
    assert reader.evaluate_ticker("T", frame, 0.0, None, stamp=stamp) is None
    assert stamp == {"reader": "new"}

    stamp = {}
    assert reader.run_eval_chain("T", frame, 0.0, None, stamp=stamp) is None
    assert stamp == {"reader": "new"}

    # The box read REFUSES the new reader out loud, as the scan does. It used to
    # read the chart, throw the read away and answer None — "no box" — on every
    # chart, so the workbench's "why did this mark miss", its grading and the
    # replay would have said "no box" to every drawing of his, looking like a
    # real answer (council review 2026-10-09, finding 2).
    stamp = {}
    with pytest.raises(NotImplementedError, match="box-only read"):
        reader.read_box(frame, 1.0, stamp=stamp)
    assert stamp == {"reader": "new"}


def test_the_scan_refuses_the_new_reader_rather_than_running_the_old_one(monkeypatch):
    """The scan's lanes reach the old engine directly and take no inner
    worker, so composing them under the new reader would hand the pool the
    OLD engine while the stamp said "new". It refuses out loud instead, and
    says where the lanes come from: the go-live plan (its words trued up by the
    council review of 2026-10-09, finding 14: it used to blame "task 12")."""
    from config import settings
    from engine_alpha import reader

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)
    with pytest.raises(NotImplementedError) as refusal:
        reader.scan_worker(near_miss_lane=True, watch_lane=False)
    assert "go-live plan" in str(refusal.value) and "task 12" not in str(refusal.value)


def test_a_frame_that_is_not_a_chart_is_a_counted_failure_not_a_crash(monkeypatch):
    """A string-date index used to escape the contract entirely: the read took
    the last day off the index BEFORE checking the frame, so it raised out of
    the reader uncaught instead of being counted."""
    from engine_alpha.evaluation import EVAL_ERROR
    from config import settings
    from engine_alpha import reader

    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", True, raising=False)
    strung = _frame()
    strung.index = [str(d.date()) for d in strung.index]
    assert reader.evaluate_ticker("T", strung, 0.0, None) is EVAL_ERROR


def test_with_the_switch_off_the_new_reader_is_never_reached(monkeypatch):
    """Flag-off output stays byte-identical — the hard rule of this build."""
    from config import settings
    from engine_alpha import reader, two_eyes

    called = []
    monkeypatch.setattr(settings, "TWO_EYES_READER_ENABLED", False, raising=False)
    monkeypatch.setattr(two_eyes, "read",
                        lambda *a, **k: called.append(a) or pytest.fail("reached"))
    reader.evaluate_ticker("TEST", _frame(), 0.0, None)
    assert not called

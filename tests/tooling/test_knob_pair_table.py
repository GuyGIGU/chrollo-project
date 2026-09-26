"""The knob pair table's operator-facing seams (council review 2026-09-01,
findings 14 and 11c):

* the settled-law registry ``conventions.md`` is SEALED against every guarded
  tool write — the guard's own EC-35 case-variant form;
* the ``--what-if`` threshold refuses non-finite and unparseable values in the
  tool's own loud style, instead of minting a fabricated flip list (a ``nan``
  threshold compares false against every mark, so every currently-passing mark
  would print as "newly refused" under a real fingerprint and epoch);
* the leg headers speak the ONE shared operator vocabulary, imported from
  ``trace_export`` rather than copied;
* and the tool's PRINTED OUTPUT itself — header, measured pair, episode clause
  and what-if flip line — is pinned, because round one's formatting work was
  guarded by nothing and a revert kept every test green (completeness pass
  2026-09-01).

Round three (completeness pass 2026-09-01) closed two holes in exactly that
surface: the episode-clause pin ran on a card whose tape was EMPTY, so it could
never separate the served summary from the raw tape (a tape-first rendering
kept the whole battery green) — it now runs on a card that completes ten rail
episodes; and the flip list, routed mark-by-mark through the pair formatter,
collapsed distinct hinge marks onto one number and printed floors its own marks
contradicted. Both are pinned below on fixtures where the defect is EXPRESSIBLE.

Round four (2026-09-01) turned that tape pin from two literal fragments into a
PROPERTY: the critic appended the tape lightly transformed ("[R S R S …]") and
all 30 tests stayed green, so the surface is now checked against the profile's
own token alphabet (derived from ``event_map._EPISODE_MARK``, never re-typed)
in ANY rendering, and the operator's line is pinned as an exact LINE.
"""
from __future__ import annotations

import os
import re
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from _paths import REPO_ROOT as ROOT
sys.path.insert(0, str(ROOT))

from engine_alpha.structure.box.box_gates import GATE_LEG_INDEX
from engine_alpha.structure.events.event_map import _EPISODE_MARK
from engine_alpha.structure.metrics.base import mark_refusal_read
from engine_alpha.structure.box.trace_export import _LEG_PHRASES
from tools import _bootstrap
from tools.calibration import knob_pair_table

# The machine tape's own alphabet, DERIVED from the reader that mints it
# (EC-33 — never a second copy): one rail letter, one mark glyph, an optional
# "~" for a verdict whose identity is not yet fixed. ``^`` (terminal posture)
# and ``~`` are declared inline in ``_profile_mark`` beside the mark table.
_PROFILE_GLYPHS = set(_EPISODE_MARK.values()) | {"^", "~"}
_PROFILE_TOKEN = re.compile(
    "[RS](?:%s)~?" % "|".join(re.escape(g) for g in sorted(_PROFILE_GLYPHS)))


def _profile_sequence_pattern(tape: str) -> re.Pattern:
    """Any rendering of a tape's RAIL SEQUENCE: its rail letters in order,
    separated by up to eight non-word characters — so the marks, quotes,
    brackets, commas and spaces a "lightly transformed" rendering introduces
    ("[R S R S …]", "['R+', 'S+', …]", "R+S+…") all still match. The order is
    the machine read; carrying it onto an operator surface in ANY spelling is
    the thing under test, not the two literal fragments round two pinned."""
    return re.compile(r"\W{0,8}".join(tok[0] for tok in tape.split()))


def test_the_settled_law_registry_is_sealed(tmp_path):
    # conventions.md is the append-only AP-*/EC-* house law and the one ruling
    # record living at the repo root — a mistyped --out must refuse, incl. the
    # EC-35 case variants (Chrollo deploys on case-insensitive NTFS).
    for law in (os.path.join(str(ROOT), "conventions.md"),
                os.path.join(str(ROOT), "Conventions.MD"),
                os.path.join(str(ROOT), "CONVENTIONS.md")):
        with pytest.raises(ValueError) as err:
            _bootstrap.refuse_sealed_output(law)
        assert "sealed" in str(err.value)
    _bootstrap.refuse_sealed_output(str(tmp_path / "pairs.json"))  # elsewhere: fine


def test_the_json_sidecar_routes_through_the_one_shared_guard():
    # EC-14: the tool's --json path is the shared refusal, never a local copy.
    assert knob_pair_table.refuse_sealed_output is _bootstrap.refuse_sealed_output


def test_what_if_refuses_a_non_finite_threshold():
    # THE defect: nan judged silently prints every passing mark as newly
    # refused — a confidently wrong flip list stamped with a real epoch.
    for bad in ("lower_dwell=nan", "lower_dwell=NaN", "lower_dwell=inf",
                "lower_dwell=-Infinity"):
        with pytest.raises(SystemExit) as err:
            knob_pair_table.parse_what_if(bad)
        assert "finite" in str(err.value)
        assert "lower_dwell=0.125" in str(err.value)   # what a valid one looks like


def test_what_if_refuses_garbage_and_a_missing_value():
    for bad in ("lower_dwell=tighter", "lower_dwell="):
        with pytest.raises(SystemExit) as err:
            knob_pair_table.parse_what_if(bad)
        assert "lower_dwell=0.125" in str(err.value)
    with pytest.raises(SystemExit) as err:
        knob_pair_table.parse_what_if("not_a_leg=0.2")
    assert "unknown leg" in str(err.value)


def test_what_if_parses_a_real_threshold():
    assert knob_pair_table.parse_what_if("lower_dwell=0.125") == (
        "lower_dwell", 0.125)
    assert knob_pair_table.parse_what_if("window=25") == ("window", 25.0)


def test_leg_headers_speak_the_shared_vocabulary():
    # Imported, never copied: every phrase this table prints is the SAME
    # wording the per-mark sentences below it render, so a signed re-wording
    # reaches the header the day it lands.
    for leg in GATE_LEG_INDEX:
        phrase = knob_pair_table.leg_phrase(leg)
        assert phrase and "{" not in phrase, leg
        assert _LEG_PHRASES[leg].startswith(phrase), leg
    # The legs whose internal id says nothing to a chart reader.
    assert knob_pair_table.leg_phrase("lower_dwell") != "lower_dwell"
    assert knob_pair_table.leg_phrase("crash") != "crash"
    assert knob_pair_table.leg_phrase("not_a_leg") == "not_a_leg"


# ── what the tool actually PRINTS ────────────────────────────────────────────


def _flat_card(ticker="TEST", R=110.0, S=100.0):
    """ONE mark card off the REAL served read — never a hand-typed leg table.
    A flat mid-box window judged at drawn rails R/S: width/window/respect/
    crash pass, the rails are never touched, so the ladder blocks at
    r_touches and the episode history is empty."""
    n, close, spread = 40, 105.0, 0.5
    closes = np.full(n, close)
    idx = pd.bdate_range("2026-01-05", periods=n)
    win = pd.DataFrame({"Open": closes, "High": closes + spread,
                        "Low": closes - spread, "Close": closes,
                        "Volume": np.full(n, 1e6)}, index=idx)
    read = mark_refusal_read(win, R, S, 1.0)
    assert read is not None
    return {"ticker": ticker, "as_of": "2026-01-05", "label": "", **read}


def _hermetic_row():
    return _flat_card()


def _episode_card():
    """A card whose EPISODE TAPE IS FULL — the fixture the round-two episode
    pin lacked. Price zig-zags rail to rail (60 trading days, a 12-day cycle
    between 102 and 148 at drawn rails 150/100), so the read completes five
    tests at resistance and four at support and the raw ``sentence`` tape is
    the machine string "R+ S+ R+ ...". On a card like this — and ONLY on a card
    like this — a tape-first rendering is visible in the printed output, which
    is what makes "the tape reaches no operator surface" a testable claim."""
    n = 60
    t = np.arange(n, dtype=float)
    close = 125.0 + 23.0 * np.sin(2 * np.pi * t / 12.0)
    idx = pd.bdate_range("2026-01-05", periods=n)
    win = pd.DataFrame({"Open": close, "High": close + 2.0, "Low": close - 2.0,
                        "Close": close, "Volume": np.full(n, 1e6)}, index=idx)
    read = mark_refusal_read(win, 150.0, 100.0, 5.0)
    assert read is not None
    assert read["sentence"], "fixture must complete episodes to express the defect"
    return {"ticker": "ZIG", "as_of": "2026-01-05", "label": "", **read}


def _run_tool(monkeypatch, capsys, *argv, rows=None):
    """Drive ``main()`` over the given cards (default: the one flat card). The
    mark LOADING is stubbed (it needs the marks DB and the frozen frame store);
    everything under test — the pair table, the vocabulary, the formatters, the
    printing — is the real code path. No session is ever opened."""
    rows = [_hermetic_row()] if rows is None else rows
    monkeypatch.setattr(knob_pair_table.database, "SessionLocal",
                        lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(knob_pair_table, "load_box_marks",
                        lambda session, ticker=None: ([], "f" * 64))
    monkeypatch.setattr(knob_pair_table, "judge_marks",
                        lambda marks: (rows, []))
    monkeypatch.setattr(sys, "argv", ["knob_pair_table", *argv])
    assert knob_pair_table.main() == 0
    return capsys.readouterr().out, rows[0]


def test_the_printed_leg_header_speaks_the_phrase_in_the_native_quantum(
        monkeypatch, capsys):
    out, row = _run_tool(monkeypatch, capsys)
    thr = {rec["leg"]: rec["threshold"] for rec in row["legs"]}
    # The thresholds are re-derived from the row (they are live knobs, not this
    # test's business); the FORMATTING is the pin — a fraction knob prints in
    # the leg's native quantum, a counted knob prints as a count.
    assert (f"coverage  (window occupancy >= {thr['coverage']:.2f})   "
            f"pass 0/1") in out
    assert f"window  (window >= {int(thr['window'])})   pass 1/1" in out


def test_the_printed_measured_pair_rides_the_shared_formatter(
        monkeypatch, capsys):
    out, _ = _run_tool(monkeypatch, capsys)
    assert "    FAIL  TEST@2026-01-05        0.17" in out    # coverage 0.1667
    assert "    PASS  TEST@2026-01-05        40" in out      # window, a count


def test_the_printed_episode_clause_is_closed_on_a_card_with_no_history(
        monkeypatch, capsys):
    """The read's ``episode_summary`` is a closed value even with NO history,
    so the line can never degrade to an em-dash the operator has to interpret.

    Scope, stated honestly: this card's tape is empty, so this test separates
    the summary from the em-dash fallback and NOTHING else — the "the raw tape
    never reaches the surface" claim is made by the test below, on a card whose
    tape is full."""
    out, row = _run_tool(monkeypatch, capsys)
    assert row["sentence"] == ""                 # the tape, empty on this card
    assert ("  TEST@2026-01-05: resistance touches 0 vs floor "
            f"{int(row['blocking_leg']['threshold'])}"
            "  |  no completed tests yet") in out
    assert "  |  —" not in out


def test_the_raw_tape_never_reaches_the_print_on_a_card_that_HAS_a_tape(
        monkeypatch, capsys):
    """The round-two pin asserted the tape was absent from a card that had no
    tape — it could only separate the summary from the em-dash fallback, and a
    tape-first rendering stayed green under it (completeness pass 2026-09-01).
    This card completes ten rail episodes, so its tape is a real string that
    WOULD appear.

    Round four (2026-09-01) makes the negatives a PROPERTY instead of two
    literal fragments: the critic appended the tape LIGHTLY TRANSFORMED to the
    per-mark line ("[R S R S …]") and ``row['sentence'] not in out`` plus
    ``'R+' not in out`` both stayed green — 30/30. The machine profile is a
    rail-letter sequence carrying event_map's declared mark glyphs, so this
    asserts against that ALPHABET however it is rendered, and pins the
    operator's line as an EXACT line rather than a substring (nothing may be
    appended to it in any spelling). Each negative is proved expressible first:
    the same patterns are run against real renderings of this card's tape and
    must MATCH there.
    """
    out, row = _run_tool(monkeypatch, capsys, rows=[_episode_card()])
    assert row["sentence"] == "R+ S+ R+ S+ R+ S+ R+ S+ R+ S+~"   # machine tape
    assert row["episode_summary"] == "5 completed tests at resistance, 4 at support"

    # (1) no PROFILE TOKEN, in the tape's own alphabet.
    assert _PROFILE_TOKEN.search(row["sentence"]), (
        "the derived alphabet no longer matches the tape it describes — the "
        "negatives below would be vacuous")
    assert not _PROFILE_TOKEN.search(out), (
        "a machine profile token reached the operator's surface: "
        f"{_PROFILE_TOKEN.search(out).group()!r}")

    # (2) no RENDERING of the tape's rail sequence — the mark glyphs stripped,
    #     re-quoted, re-bracketed or re-joined all still carry the machine
    #     read's order onto a surface that is supposed to speak plain words.
    seq = _profile_sequence_pattern(row["sentence"])
    for rendering in (row["sentence"],                            # verbatim
                      str(row["sentence"].split()),               # ['R+', …]
                      str([t[0] for t in row["sentence"].split()]),  # ['R', …]
                      " ".join(t[0] for t in row["sentence"].split()),  # R S R
                      row["sentence"].replace(" ", "")):          # R+S+R+…
        assert seq.search(rendering), f"expressible-check failed: {rendering}"
    assert not seq.search(out), "the tape's rail sequence reached the print"

    # (3) and the operator's line is EXACTLY the two served phrases — a
    #     substring check admits anything appended after them.
    line = [ln for ln in out.splitlines() if ln.startswith("  ZIG@")]
    assert line == ["  ZIG@2026-01-05: box height 0.50 of price vs cap 0.18"
                    "  |  5 completed tests at resistance, 4 at support"]


def test_the_printed_what_if_flip_line_rides_the_shared_formatter(
        monkeypatch, capsys):
    out, _ = _run_tool(monkeypatch, capsys, "--what-if", "coverage=0.16")
    assert "WHAT-IF coverage (window occupancy) -> 0.16:" in out
    assert "  newly admitted: ['TEST@2026-01-05 (0.17)']" in out
    assert "  newly refused:  —" in out


# ── one precision per printed block (completeness pass 2026-09-01) ───────────


def _dwell_rows(*measured, floor=0.15):
    """Rows carrying one leg each at the standing floor — the shape
    ``what_if_flips`` consumes, so the pin runs the real derivation. ``ok`` is
    the leg's own comparison, never hand-set, so a fixture cannot claim a
    verdict the threshold contradicts."""
    return [{"ticker": f"M{i}", "as_of": "2026-02-10", "legs": [
        {"leg": "lower_dwell", "measured": m, "threshold": floor,
         "ok": m >= floor}]} for i, m in enumerate(measured)]


def test_distinct_hinge_marks_never_collapse_onto_one_number():
    """THE regression round two introduced: routing each mark through the PAIR
    formatter compares it against the floor alone, so 0.118, 0.121 and 0.1249
    all differ from a proposed 0.10 at two decimals and all printed "(0.12)" —
    three different marks, one number, on exactly the marks a ruling turns on.
    One precision for the whole block keeps them apart."""
    flips = knob_pair_table.what_if_flips(_dwell_rows(0.118, 0.121, 0.1249),
                                          "lower_dwell", 0.10)
    assert flips["newly_admitted"] == ["M0@2026-02-10 (0.118)",
                                       "M1@2026-02-10 (0.121)",
                                       "M2@2026-02-10 (0.125)"]
    shown = [name.split("(")[1] for name in flips["newly_admitted"]]
    assert len(set(shown)) == 3
    assert flips["newly_refused"] == []


def test_a_flip_entry_is_never_arithmetically_impossible_against_its_floor():
    """The other half: a mark at 0.1449 widened to "(0.1449)" against the
    proposal while the header floor, formatted ALONE, printed "0.14" — an
    operator reading a mark at 0.1449 refused by a floor of 0.14. The floor now
    prints at the block's own precision, so the line reads true."""
    flips = knob_pair_table.what_if_flips(_dwell_rows(0.1449, floor=0.10),
                                          "lower_dwell", 0.145)
    assert flips["newly_refused"] == ["M0@2026-02-10 (0.1449)"]
    assert flips["proposed_shown"] == "0.1450"          # never "0.14"
    assert float("0.1449") < float(flips["proposed_shown"])   # >= floor: refused


def test_the_block_precision_leaves_the_ordinary_case_at_two_decimals():
    """Widening is the exception, not the house style: nothing collides here,
    so every number stays at the shared formatter's two decimals."""
    flips = knob_pair_table.what_if_flips(_dwell_rows(0.30, 0.42), "lower_dwell",
                                          0.35)
    assert flips["newly_refused"] == ["M0@2026-02-10 (0.30)"]
    assert flips["proposed_shown"] == "0.35"


def test_counted_legs_stay_counts_in_a_block():
    counted = [{"ticker": "WIN", "as_of": "2026-02-11", "legs": [
        {"leg": "window", "measured": 41, "threshold": 30, "ok": True}]}]
    flips = knob_pair_table.what_if_flips(counted, "window", 45)
    assert flips["newly_refused"] == ["WIN@2026-02-11 (41)"]   # never 41.00
    assert flips["proposed_shown"] == "45"


def test_fmt_block_is_the_one_rule_both_printed_blocks_use():
    assert knob_pair_table.fmt_block([0.118, 0.121, 0.1249], 0.10, "fraction") \
        == (["0.118", "0.121", "0.125"], "0.100")
    assert knob_pair_table.fmt_block([0.1449], 0.145, "fraction") \
        == (["0.1449"], "0.1450")
    assert knob_pair_table.fmt_block([41], 30, "bars") == (["41"], "30")
    assert knob_pair_table.fmt_block([], 0.145, "fraction") == ([], "0.14")
    # Equal values are not a collision — one number may legitimately repeat.
    assert knob_pair_table.fmt_block([0.15, 0.15], 0.15, "fraction") \
        == (["0.15", "0.15"], "0.15")


def test_the_printed_what_if_header_carries_the_block_floor(
        monkeypatch, capsys):
    """End to end on a REAL read card: the middle-third dwell measures 0.1667
    and a proposed cap of 0.165 refuses it. Both round to "0.17" at two
    decimals, so the block widens — and the header must widen WITH it. Before
    this fix the operator read "-> 0.17" above a mark refused at 0.167."""
    out, _ = _run_tool(monkeypatch, capsys, "--what-if", "mid_dwell=0.165",
                       rows=[_episode_card()])
    assert "WHAT-IF mid_dwell (time in the middle third) -> 0.165:" in out
    assert "  newly refused:  ['ZIG@2026-01-05 (0.167)']" in out
    assert "-> 0.17:" not in out          # the impossible floor, gone


def test_the_printed_pair_table_never_collapses_two_hinge_marks(
        monkeypatch, capsys):
    """The same rule on the table above the flip list: two marks drawn at
    rails a tenth of a point apart measure 0.105 and 0.104 box height. Both
    render "0.10" at two decimals — two different marks printed as one number,
    in the table whose whole job is showing where each mark sits."""
    rows = [_flat_card("WIDE", R=110.5), _flat_card("NARR", R=110.4)]
    out, _ = _run_tool(monkeypatch, capsys, rows=rows)
    assert "    PASS  WIDE@2026-01-05        0.105" in out
    assert "    PASS  NARR@2026-01-05        0.104" in out
    assert "        0.10\n" not in out       # the collapsed pair, gone
    assert "width  (box height <= 0.180)   pass 2/2" in out   # the floor, same block


def test_the_what_if_refusal_never_reaches_the_marks(monkeypatch, capsys):
    """The nan pre-flight fires BEFORE a single mark is scored — the refusal
    the operator sees instead of a fabricated flip list."""
    monkeypatch.setattr(sys, "argv",
                        ["knob_pair_table", "--what-if", "coverage=nan"])
    with pytest.raises(SystemExit) as err:
        knob_pair_table.main()
    assert "finite" in str(err.value)
    assert capsys.readouterr().out == ""
